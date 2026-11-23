package ckpt.sim;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.cloudbus.cloudsim.Cloudlet;
import org.cloudbus.cloudsim.DatacenterBroker;
import org.cloudbus.cloudsim.DatacenterCharacteristics;
import org.cloudbus.cloudsim.Host;
import org.cloudbus.cloudsim.UtilizationModelFull;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.core.CloudSimTags;
import org.cloudbus.cloudsim.core.SimEvent;

import ckpt.policy.CheckpointPolicy;
import ckpt.policy.RiskTier;

/**
 * Broker that runs work streams with checkpointing, failure handling and recovery.
 *
 * Workload model: every stream has a PREDETERMINED job list (ids, lengths, submit times) shared by all
 * policies. Jobs arrive at their submit times, wait in the stream's FIFO queue while the host is busy,
 * and every submitted job runs to completion (late jobs are recorded as deadline misses, never skipped).
 *
 * Execution model (CloudSim 3.0.3 pause/resume is not used - see SETUP_LOG.md, section 6):
 *  - A job is executed as a chain of COMPUTE segment cloudlets on the stream's current VM.
 *    A segment ends at the earliest of: job completion, the next checkpoint due time, the next
 *    midnight (so a new daily risk tier takes effect at 00:00 at the latest).
 *  - A checkpoint is a CHECKPOINT cloudlet of C seconds on the same VM. Work is committed only when
 *    that cloudlet completes; a failure during the write loses that checkpoint.
 *  - On a host failure the running cloudlet is cancelled, progress at the failure instant is computed
 *    exactly from the segment start time (dedicated 1-PE VM), lost work = progress - committed,
 *    and the stream is moved to a spare VM. After D + B seconds a RESTORE cloudlet of R seconds runs
 *    (only if a checkpoint exists) and execution continues from the committed work.
 *  - Checkpoint intervals are measured from the last completed checkpoint (or job (re)start).
 */
public final class CheckpointingBroker extends DatacenterBroker {
    public static final double DAY = 86400.0;
    private static final double EPS = 1e-6;
    private static final double MIN_SEGMENT_SEC = 1.0;
    public static final int JOB_ARRIVAL = 910004;

    /** IDLE = no job running; RECOVERING = replacement host not ready yet (D + B). */
    enum Phase { IDLE, RUN, CHECKPOINT, RECOVERING, RESTORE }

    enum Kind { COMPUTE, CHECKPOINT, RESTORE }

    static final class Seg {
        final int streamId;
        final Kind kind;
        final double startTime;
        final double workSec;
        final boolean endsAtDue;

        Seg(int streamId, Kind kind, double startTime, double workSec, boolean endsAtDue) {
            this.streamId = streamId;
            this.kind = kind;
            this.startTime = startTime;
            this.workSec = workSec;
            this.endsAtDue = endsAtDue;
        }
    }

    private final SimParams p;
    private final CheckpointPolicy policy;
    private final List<StreamSpec> streams;

    // VM plan (set by SimulationRunner before the simulation starts)
    private Map<Integer, Integer> datacenterOfVm;
    private Map<Integer, Host> hostOfVm;
    private final Deque<Integer> spareVms = new ArrayDeque<Integer>();
    private int vmAcks;

    // per-stream state
    private final int n;
    private final Phase[] phase;
    private final int[] vmOf;
    private final boolean[] onSpare;
    private final boolean[] primaryFailed;
    private final int[] nextArrival;                 // index of the next job to arrive
    private final List<Deque<JobRecord>> queue = new ArrayList<Deque<JobRecord>>();   // arrived, not started
    private final JobRecord[] cur;
    private final double[] progress;
    private final double[] committed;
    private final double[] pendingCommit;
    private final double[] lastCkptTime;
    private final int[] curCloudlet;

    private final Map<Integer, Seg> segById = new HashMap<Integer, Seg>();
    private final List<JobRecord> records = new ArrayList<JobRecord>();
    private int nextCloudletId;

    // diagnostics
    public int failuresApplied;            // failures that interrupted running work
    public int failuresWhileIdleOrDone;    // primary failed while stream idle/finished/not started
    public long cloudletsSubmitted;
    public final List<String> trace = new ArrayList<String>();   // optional event log (tests)
    public boolean keepTrace;
    public EventLog events;                                      // optional structured logs (pilot)

    public CheckpointingBroker(String name, SimParams p, CheckpointPolicy policy, List<StreamSpec> streams)
            throws Exception {
        super(name);
        this.p = p;
        this.policy = policy;
        this.streams = streams;
        this.n = streams.size();
        phase = new Phase[n];
        vmOf = new int[n];
        onSpare = new boolean[n];
        primaryFailed = new boolean[n];
        nextArrival = new int[n];
        cur = new JobRecord[n];
        progress = new double[n];
        committed = new double[n];
        pendingCommit = new double[n];
        lastCkptTime = new double[n];
        curCloudlet = new int[n];
        for (int s = 0; s < n; s++) {
            if (streams.get(s).streamId != s) {
                throw new IllegalArgumentException("streamId must equal list position");
            }
            phase[s] = Phase.IDLE;
            vmOf[s] = s;               // VM s / host s is the primary host of stream s
            curCloudlet[s] = -1;
            queue.add(new ArrayDeque<JobRecord>());
        }
    }

    public void setVmPlan(Map<Integer, Integer> datacenterOfVm, Map<Integer, Host> hostOfVm, List<Integer> spares) {
        this.datacenterOfVm = datacenterOfVm;
        this.hostOfVm = hostOfVm;
        this.spareVms.addAll(spares);
    }

    public List<JobRecord> getRecords() {
        return records;
    }

    public int sparesLeft() {
        return spareVms.size();
    }

    // ------------------------------------------------------------------ startup: create all VMs
    @Override
    protected void processResourceCharacteristics(SimEvent ev) {
        DatacenterCharacteristics c = (DatacenterCharacteristics) ev.getData();
        getDatacenterCharacteristicsList().put(c.getId(), c);
        if (getDatacenterCharacteristicsList().size() == getDatacenterIdsList().size()) {
            for (Vm vm : getVmList()) {
                sendNow(datacenterOfVm.get(vm.getId()), CloudSimTags.VM_CREATE_ACK, vm);
            }
        }
    }

    @Override
    protected void processVmCreate(SimEvent ev) {
        int[] data = (int[]) ev.getData();
        if (data[2] != CloudSimTags.TRUE) {
            throw new IllegalStateException("VM " + data[1] + " could not be created");
        }
        getVmsToDatacentersMap().put(data[1], data[0]);
        if (++vmAcks == getVmList().size()) {
            for (int s = 0; s < n; s++) {
                scheduleNextArrival(s);
            }
        }
    }

    // ------------------------------------------------------------------ arrivals, queue, job start
    /** Arrivals are chained: each arrival schedules the next one at its predetermined submit time. */
    private void scheduleNextArrival(int s) {
        List<JobSpec> jobs = streams.get(s).jobs;
        if (nextArrival[s] >= jobs.size()) {
            return;
        }
        double delay = Math.max(0.0, jobs.get(nextArrival[s]).submitTime - CloudSim.clock());
        schedule(getId(), delay, JOB_ARRIVAL, Integer.valueOf(s));
    }

    private void onArrival(int s) {
        JobSpec spec = streams.get(s).jobs.get(nextArrival[s]++);
        JobRecord r = new JobRecord(s, spec, p.deadlineFactor);   // submit time = predetermined time
        records.add(r);
        queue.get(s).addLast(r);
        log(s, "arrival " + spec.jobId + " L=" + spec.lengthSec);
        scheduleNextArrival(s);
        tryStart(s);
    }

    /** Start the oldest queued job if the stream's host is free (FIFO, one job at a time). */
    private void tryStart(int s) {
        if (phase[s] != Phase.IDLE || cur[s] != null || queue.get(s).isEmpty()) {
            return;
        }
        double now = CloudSim.clock();
        JobRecord r = queue.get(s).pollFirst();
        r.startTime = now;
        r.hostsUsed.add(vmOf[s]);
        cur[s] = r;
        progress[s] = 0;
        committed[s] = 0;
        lastCkptTime[s] = now;
        phase[s] = Phase.RUN;
        log(s, "job " + r.jobIndex + " start L=" + r.lengthSec + " on vm " + vmOf[s] + " queued="
                + (now - r.submitTime));
        nextSegment(s);
    }

    private RiskTier currentTier(int s, double now) {
        return onSpare[s] ? RiskTier.MEDIUM : streams.get(s).risk.tierAt(now);
    }

    private void nextSegment(int s) {
        double now = CloudSim.clock();
        double remaining = cur[s].lengthSec - progress[s];
        if (remaining <= EPS) {
            completeJob(s);
            return;
        }
        double interval = policy.intervalSeconds(currentTier(s, now));
        double due = lastCkptTime[s] + interval;
        if (due <= now + EPS && progress[s] > committed[s] + EPS) {
            startCheckpoint(s);      // e.g. the tier tightened at midnight and a checkpoint is overdue
            return;
        }
        double nextMidnight = (Math.floor(now / DAY) + 1) * DAY;
        if (nextMidnight - now < MIN_SEGMENT_SEC) {
            nextMidnight += DAY;
        }
        double len = remaining;
        boolean endsAtDue = false;
        if (due - now < len) {
            len = Math.max(due - now, MIN_SEGMENT_SEC);
            endsAtDue = true;
        }
        if (nextMidnight - now < len) {
            len = nextMidnight - now;
            endsAtDue = false;
        }
        // Never leave a sub-second remainder: CloudSim 3.0.3 can drop completion of cloudlets shorter than
        // minTimeBetweenEvents (Datacenter.updateCloudletProcessing skips updates within that window).
        if (remaining - len < MIN_SEGMENT_SEC) {
            len = remaining;
            endsAtDue = false;
        }
        submit(s, Kind.COMPUTE, len, endsAtDue);
    }

    private void startCheckpoint(int s) {
        pendingCommit[s] = progress[s];
        phase[s] = Phase.CHECKPOINT;
        submit(s, Kind.CHECKPOINT, p.checkpointSec, false);
    }

    private void completeJob(int s) {
        cur[s].finishTime = CloudSim.clock();
        log(s, "job " + cur[s].jobIndex + " finished; ckpts=" + cur[s].checkpoints + " failures=" + cur[s].failures);
        cur[s] = null;
        phase[s] = Phase.IDLE;
        tryStart(s);
    }

    private void submit(int s, Kind kind, double seconds, boolean endsAtDue) {
        long mi = Math.max(1L, Math.round(seconds * p.mips));
        double workSec = mi / p.mips;
        int id = nextCloudletId++;
        Cloudlet cl = new Cloudlet(id, mi, 1, 1, 1, new UtilizationModelFull(), new UtilizationModelFull(),
                new UtilizationModelFull());
        cl.setUserId(getId());
        cl.setVmId(vmOf[s]);
        segById.put(id, new Seg(s, kind, CloudSim.clock(), workSec, endsAtDue));
        curCloudlet[s] = id;
        cloudletsSubmitted++;
        sendNow(datacenterOfVm.get(vmOf[s]), CloudSimTags.CLOUDLET_SUBMIT, cl);
    }

    @Override
    protected void processCloudletReturn(SimEvent ev) {
        Cloudlet cl = (Cloudlet) ev.getData();
        Seg seg = segById.remove(cl.getCloudletId());
        if (seg == null) {
            return;                                    // cancelled earlier
        }
        int s = seg.streamId;
        if (curCloudlet[s] != cl.getCloudletId() || cl.getCloudletStatus() != Cloudlet.SUCCESS) {
            return;                                    // stale (host failed) - ignore
        }
        curCloudlet[s] = -1;
        double now = CloudSim.clock();
        switch (seg.kind) {
            case COMPUTE:
                progress[s] += seg.workSec;
                if (cur[s].lengthSec - progress[s] <= EPS) {
                    completeJob(s);
                } else if (seg.endsAtDue) {
                    startCheckpoint(s);
                } else {
                    nextSegment(s);
                }
                break;
            case CHECKPOINT:
                committed[s] = pendingCommit[s];
                cur[s].checkpoints++;
                cur[s].checkpointOverheadSec += p.checkpointSec;
                lastCkptTime[s] = now;
                phase[s] = Phase.RUN;
                log(s, "checkpoint committed=" + committed[s]);
                if (events != null) {
                    events.checkpoint(now, s, streams.get(s).label, cur[s].jobIndex, committed[s], vmOf[s],
                            currentTier(s, seg.startTime).name());
                }
                nextSegment(s);
                break;
            case RESTORE:
                phase[s] = Phase.RUN;
                lastCkptTime[s] = now;
                log(s, "restored committed=" + committed[s] + " on vm " + vmOf[s]);
                if (events != null) {
                    events.recovery(now, s, streams.get(s).label, cur[s].jobIndex, "restore_completed", vmOf[s],
                            committed[s]);
                }
                nextSegment(s);
                break;
            default:
                throw new IllegalStateException();
        }
    }

    // ------------------------------------------------------------------ failures and recovery
    private void onHostFailure(int s) {
        double now = CloudSim.clock();
        if (primaryFailed[s]) {
            throw new IllegalStateException("primary host of stream " + s + " failed twice");
        }
        primaryFailed[s] = true;
        hostOfVm.get(s).setFailed(true);
        if (onSpare[s]) {
            throw new IllegalStateException("stream already on a spare when its primary failed");
        }
        if (phase[s] == Phase.IDLE) {
            // no job running: nothing is lost, but the replacement still needs D + B before it can run jobs
            failuresWhileIdleOrDone++;
            int idleFailedVm = vmOf[s];
            vmOf[s] = takeSpare();
            onSpare[s] = true;
            phase[s] = Phase.RECOVERING;
            log(s, "primary host failed while IDLE - no work lost -> spare vm " + vmOf[s]);
            if (events != null) {
                events.failure(now, s, streams.get(s).label, -1, "IDLE", 0, 0, 0, 0, idleFailedVm, vmOf[s]);
            }
            schedule(getId(), p.detectSec + p.bootSec, CkptTags.RECOVERY_READY, Integer.valueOf(s));
            return;
        }
        // phases RECOVERING / RESTORE only occur on spare hosts, which never fail
        Seg seg = segById.remove(curCloudlet[s]);
        double progressAtFail;
        double interrupted = 0.0;
        Phase phaseAtFail = phase[s];
        int failedVm = vmOf[s];
        if (phase[s] == Phase.RUN) {
            double done = Math.min(Math.max(now - seg.startTime, 0.0), seg.workSec);
            progressAtFail = progress[s] + done;
        } else if (phase[s] == Phase.CHECKPOINT) {
            progressAtFail = progress[s];                       // checkpoint write lost
            interrupted = Math.max(now - seg.startTime, 0.0);
            cur[s].lostCheckpointWriteSec += interrupted;
        } else {
            throw new IllegalStateException("unexpected phase " + phase[s]);
        }
        double lost = progressAtFail - committed[s];
        cur[s].lostWorkSec += lost;
        cur[s].failures++;
        failuresApplied++;
        sendNow(datacenterOfVm.get(vmOf[s]), CloudSimTags.CLOUDLET_CANCEL,
                new int[] {curCloudlet[s], getId(), vmOf[s]});
        curCloudlet[s] = -1;
        progress[s] = committed[s];
        phase[s] = Phase.RECOVERING;
        vmOf[s] = takeSpare();
        onSpare[s] = true;
        log(s, "HOST FAILURE: progress=" + progressAtFail + " committed=" + committed[s] + " lost=" + lost
                + " -> spare vm " + vmOf[s]);
        if (events != null) {
            events.failure(now, s, streams.get(s).label, cur[s].jobIndex, phaseAtFail.name(), progressAtFail,
                    committed[s], lost, interrupted, failedVm, vmOf[s]);
        }
        schedule(getId(), p.detectSec + p.bootSec, CkptTags.RECOVERY_READY, Integer.valueOf(s));
    }

    private int takeSpare() {
        Integer v = spareVms.poll();
        if (v == null) {
            throw new IllegalStateException("spare pool exhausted");
        }
        return v;
    }

    private void onRecoveryReady(int s) {
        if (cur[s] == null) {                      // the failure happened while idle
            if (events != null) {
                events.recovery(CloudSim.clock(), s, streams.get(s).label, -1, "replacement_ready_idle", vmOf[s], 0);
            }
            phase[s] = Phase.IDLE;
            tryStart(s);
            return;
        }
        cur[s].hostsUsed.add(vmOf[s]);
        if (events != null) {
            events.recovery(CloudSim.clock(), s, streams.get(s).label, cur[s].jobIndex,
                    committed[s] > EPS ? "replacement_ready_restore" : "replacement_ready_restart", vmOf[s],
                    committed[s]);
        }
        if (committed[s] > EPS) {
            cur[s].recoverySec += p.detectSec + p.bootSec + p.restoreSec;
            phase[s] = Phase.RESTORE;
            submit(s, Kind.RESTORE, p.restoreSec, false);
        } else {
            cur[s].recoverySec += p.detectSec + p.bootSec;    // nothing to restore: restart from zero
            phase[s] = Phase.RUN;
            lastCkptTime[s] = CloudSim.clock();
            log(s, "restart from zero on vm " + vmOf[s]);
            nextSegment(s);
        }
    }

    @Override
    protected void processOtherEvent(SimEvent ev) {
        switch (ev.getTag()) {
            case CkptTags.HOST_FAILURE:
                onHostFailure((Integer) ev.getData());
                break;
            case CkptTags.RECOVERY_READY:
                onRecoveryReady((Integer) ev.getData());
                break;
            case JOB_ARRIVAL:
                onArrival((Integer) ev.getData());
                break;
            case CloudSimTags.CLOUDLET_CANCEL:   // datacenter echo of a cancellation - nothing to do
                break;
            default:
                throw new IllegalStateException("unexpected event tag " + ev.getTag());
        }
    }

    private void log(int s, String msg) {
        if (keepTrace) {
            trace.add(String.format("%12.2f  stream %d  %s", CloudSim.clock(), s, msg));
        }
    }
}
