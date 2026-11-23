package ckpt.sim;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.HashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;

import org.cloudbus.cloudsim.CloudletSchedulerSpaceShared;
import org.cloudbus.cloudsim.Datacenter;
import org.cloudbus.cloudsim.DatacenterCharacteristics;
import org.cloudbus.cloudsim.Host;
import org.cloudbus.cloudsim.Log;
import org.cloudbus.cloudsim.Pe;
import org.cloudbus.cloudsim.Storage;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.VmSchedulerTimeShared;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.provisioners.BwProvisionerSimple;
import org.cloudbus.cloudsim.provisioners.PeProvisionerSimple;
import org.cloudbus.cloudsim.provisioners.RamProvisionerSimple;

import ckpt.policy.CheckpointPolicy;

/**
 * Builds one CloudSim 3.0.3 simulation:
 *   hosts 0..n-1      = primary hosts (host s <-> stream s <-> one Backblaze drive)
 *   hosts n..n+k-1    = spare (replacement) hosts; never fail
 * every host: 1 PE at p.mips; every VM: 1 PE at p.mips, space-shared cloudlet scheduler.
 * Hosts are grouped into Datacenter entities of p.hostsPerDatacenter hosts each.
 */
public final class SimulationRunner {

    public static final class Result {
        public final String policy;
        public final List<JobRecord> records;
        public final int failuresScheduled;
        public final int failuresFired;
        public final int failuresApplied;
        public final int failuresWhileIdleOrDone;
        public final long cloudletsSubmitted;
        public final double simEndTime;
        public final long wallMillis;
        public final Map<Integer, Boolean> hostFailedFlag;   // final Host.isFailed() per host index
        public final List<String> trace;

        Result(String policy, List<JobRecord> records, int scheduled, int fired, int applied, int idle,
               long submitted, double end, long wall, Map<Integer, Boolean> failed, List<String> trace) {
            this.policy = policy;
            this.records = records;
            this.failuresScheduled = scheduled;
            this.failuresFired = fired;
            this.failuresApplied = applied;
            this.failuresWhileIdleOrDone = idle;
            this.cloudletsSubmitted = submitted;
            this.simEndTime = end;
            this.wallMillis = wall;
            this.hostFailedFlag = failed;
            this.trace = trace;
        }
    }

    private SimulationRunner() {
    }

    public static Result run(SimParams p, CheckpointPolicy policy, List<StreamSpec> streams,
                             List<FailureEvent> failures, int spareHosts, boolean keepTrace) throws Exception {
        return run(p, policy, streams, failures, spareHosts, keepTrace, null);
    }

    public static Result run(SimParams p, CheckpointPolicy policy, List<StreamSpec> streams,
                             List<FailureEvent> failures, int spareHosts, boolean keepTrace, EventLog events)
            throws Exception {
        long t0 = System.currentTimeMillis();
        Log.disable();
        CloudSim.init(1, Calendar.getInstance(), false);

        int n = streams.size();
        int total = n + spareHosts;
        Map<Integer, Host> hostOfVm = new HashMap<Integer, Host>();
        List<List<Host>> groups = new ArrayList<List<Host>>();
        for (int i = 0; i < total; i++) {
            if (i % p.hostsPerDatacenter == 0) {
                groups.add(new ArrayList<Host>());
            }
            List<Pe> pes = new ArrayList<Pe>();
            pes.add(new Pe(0, new PeProvisionerSimple(p.mips)));
            Host h = new Host(i, new RamProvisionerSimple(4096), new BwProvisionerSimple(10000), 1000000, pes,
                    new VmSchedulerTimeShared(pes));
            groups.get(groups.size() - 1).add(h);
            hostOfVm.put(i, h);
        }
        Map<Integer, Integer> datacenterOfVm = new HashMap<Integer, Integer>();
        int vmIndex = 0;
        for (int g = 0; g < groups.size(); g++) {
            List<Host> hs = groups.get(g);
            Map<Integer, Host> local = new HashMap<Integer, Host>();
            for (Host h : hs) {
                local.put(h.getId(), h);
            }
            DatacenterCharacteristics ch = new DatacenterCharacteristics("x86", "Linux", "Xen", hs, 0.0, 0, 0, 0, 0);
            Datacenter dc = new Datacenter("DC_" + g, ch, new IdMappedVmAllocationPolicy(hs, local),
                    new LinkedList<Storage>(), 0);
            for (int k = 0; k < hs.size(); k++) {
                datacenterOfVm.put(vmIndex++, dc.getId());
            }
        }

        CheckpointingBroker broker = new CheckpointingBroker("Broker", p, policy, streams);
        broker.keepTrace = keepTrace;
        broker.events = events;
        List<Vm> vms = new ArrayList<Vm>();
        List<Integer> spares = new ArrayList<Integer>();
        for (int i = 0; i < total; i++) {
            vms.add(new Vm(i, broker.getId(), p.mips, 1, 1024, 1000, 10000, "Xen", new CloudletSchedulerSpaceShared()));
            if (i >= n) {
                spares.add(i);
            }
        }
        broker.submitVmList(vms);
        broker.setVmPlan(datacenterOfVm, hostOfVm, spares);

        FailureInjector injector = new FailureInjector("FailureInjector", failures);
        injector.setBrokerId(broker.getId());

        double end = CloudSim.startSimulation();
        CloudSim.stopSimulation();

        // Every PLANNED job must have been submitted, and every submitted job must have finished
        // (the simulation runs until no events remain; nothing is skipped).
        int planned = 0;
        for (StreamSpec sp : streams) {
            planned += sp.jobs.size();
        }
        if (broker.getRecords().size() != planned) {
            throw new IllegalStateException("submitted " + broker.getRecords().size() + " of " + planned
                    + " planned jobs");
        }
        for (JobRecord r : broker.getRecords()) {
            if (!r.finished()) {
                throw new IllegalStateException("job " + r.jobId + " was submitted but never finished"
                        + " - simulation stalled");
            }
        }
        Map<Integer, Boolean> failed = new HashMap<Integer, Boolean>();
        for (Map.Entry<Integer, Host> e : hostOfVm.entrySet()) {
            failed.put(e.getKey(), e.getValue().isFailed());
        }
        return new Result(policy.name(), broker.getRecords(), failures.size(), injector.getFired(),
                broker.failuresApplied, broker.failuresWhileIdleOrDone, broker.cloudletsSubmitted, end,
                System.currentTimeMillis() - t0, failed, broker.trace);
    }
}
