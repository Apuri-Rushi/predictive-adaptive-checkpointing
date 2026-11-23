package ckpt;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.lang.management.MemoryType;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import ckpt.policy.CheckpointPolicy;
import ckpt.policy.Policies;
import ckpt.policy.RiskTierClassifier;
import ckpt.risk.DailyScoreTimeline;
import ckpt.sim.EventLog;
import ckpt.sim.FailureEvent;
import ckpt.sim.JobRecord;
import ckpt.sim.JobSpec;
import ckpt.sim.SimParams;
import ckpt.sim.SimulationRunner;
import ckpt.sim.StreamSpec;
import ckpt.trace.FailureTraceLoader;
import ckpt.trace.FailureTraceLoader.TraceFailure;
import ckpt.trace.Hashing;
import ckpt.trace.RiskTraceLoader;
import ckpt.trace.WorkloadGenerator;

/**
 * Trace-driven experiment for ONE shard: crc32(serial) % shards == shard.
 *
 * Usage:
 *   ExperimentRunner --predictions <test_predictions.csv.gz> --failures <drive_failure_summary.csv>
 *                    --out <dir> [--shard 0] [--shards 56] [--t0 1,4,12,24,72] [--policies E1,E2,E3]
 *                    [--hosts-per-dc 50] [--no-failures]
 *
 * Data flow (leakage control):
 *   predictions -> RiskTraceLoader (serial, date, score only) -> DailyScoreTimeline -> policy
 *   failure file -> FailureTraceLoader -> FailureEvent list -> FailureInjector ONLY
 */
public final class ExperimentRunner {
    static final double DAY = 86400.0;
    static final double HORIZON = 30 * DAY;          // no new job starts at/after 2019-07-01 00:00

    public static void main(String[] a) throws Exception {
        Map<String, String> arg = new HashMap<String, String>();
        for (int i = 0; i < a.length; i++) {
            if (a[i].equals("--no-failures")) {
                arg.put("no-failures", "true");
            } else {
                arg.put(a[i].substring(2), a[++i]);
            }
        }
        File pred = new File(arg.get("predictions"));
        File failFile = new File(arg.get("failures"));
        File out = new File(arg.get("out"));
        int shard = Integer.parseInt(get(arg, "shard", "0"));
        int shards = Integer.parseInt(get(arg, "shards", "56"));
        int perDc = Integer.parseInt(get(arg, "hosts-per-dc", "50"));
        String[] t0s = get(arg, "t0", "1,4,12,24,72").split(",");
        String policySet = get(arg, "policies", "E1,E2,E3");
        double rho = Double.parseDouble(get(arg, "utilization", "1.0"));   // 1.0 = nominal back-to-back
        boolean noFailures = arg.containsKey("no-failures");
        if (!out.isDirectory() && !out.mkdirs()) {
            throw new IOException("cannot create " + out);
        }

        // ---------------------------------------------------------------- inputs
        long t0 = System.currentTimeMillis();
        RiskTraceLoader.Loaded L = RiskTraceLoader.load(pred, shard, shards, RiskTierClassifier.approved());
        List<String> serials = new ArrayList<String>(L.timelines.keySet());          // sorted
        Map<String, Integer> streamOf = new HashMap<String, Integer>();
        List<StreamSpec> streams = new ArrayList<StreamSpec>();
        // WORKLOAD: generated ONCE here, before any policy runs, and shared by every policy run.
        StringBuilder st = new StringBuilder("stream,serial,primary_host,first_day,start_time,score_count,jobs\n");
        StringBuilder wl = new StringBuilder("job_id,stream,serial,primary_host,job_index,length_sec,submit_time\n");
        int plannedJobs = 0;
        for (int s = 0; s < serials.size(); s++) {
            String ser = serials.get(s);
            streamOf.put(ser, s);
            int first = L.firstDay.get(ser);
            double start = Math.max(0, first) * DAY;                   // 00:00 of first observed day
            List<JobSpec> jobs = WorkloadGenerator.plan(ser, start, HORIZON, rho);
            plannedJobs += jobs.size();
            streams.add(new StreamSpec(s, ser, jobs, L.timelines.get(ser)));
            st.append(s).append(',').append(ser).append(',').append(s).append(',').append(first).append(',')
                    .append(f(start)).append(',').append(L.scoreCount.get(ser)).append(',').append(jobs.size())
                    .append('\n');
            for (JobSpec j : jobs) {
                wl.append(j.jobId).append(',').append(s).append(',').append(ser).append(',').append(s).append(',')
                        .append(j.index).append(',').append(f(j.lengthSec)).append(',').append(f(j.submitTime))
                        .append('\n');
            }
        }
        writeText(new File(out, "streams.csv"), st.toString());
        writeText(new File(out, "workload.csv"), wl.toString());

        // daily tier in force at 00:00 of each day (d+1 rule + carry-forward), for validation
        StringBuilder tt = new StringBuilder("stream,serial,day,score_in_force,tier\n");
        for (int s = 0; s < serials.size(); s++) {
            DailyScoreTimeline tl = L.timelines.get(serials.get(s));
            for (int d = 0; d <= 37; d++) {
                double sc = tl.scoreAt(d * DAY);
                tt.append(s).append(',').append(serials.get(s)).append(',').append(d).append(',')
                        .append(Double.isNaN(sc) ? "" : String.format(Locale.ROOT, "%.9g", sc)).append(',')
                        .append(tl.tierAt(d * DAY)).append('\n');
            }
        }
        writeText(new File(out, "tier_timeline.csv"), tt.toString());

        List<FailureEvent> failures = new ArrayList<FailureEvent>();
        StringBuilder fl = new StringBuilder("stream,serial,failure_day,t_fail\n");
        if (!noFailures) {
            for (TraceFailure f : FailureTraceLoader.load(failFile, new HashSet<String>(serials))) {
                int s = streamOf.get(f.serial);
                failures.add(new FailureEvent(s, f.time));
                fl.append(s).append(',').append(f.serial).append(',').append(f.day).append(',')
                        .append(String.format(Locale.ROOT, "%.1f", f.time)).append('\n');
            }
        }
        writeText(new File(out, "injector_failures.csv"), fl.toString());
        String workloadHash = Hashing.sha256(wl.toString());
        String failureHash = Hashing.sha256(fl.toString());
        String tierHash = Hashing.sha256(tt.toString());
        long loadMs = System.currentTimeMillis() - t0;

        Map<String, Object> info = new LinkedHashMap<String, Object>();
        info.put("shard", shard);
        info.put("shards", shards);
        info.put("hosts", serials.size());
        info.put("prediction_rows_read", L.rowsRead);
        info.put("prediction_rows_kept", L.rowsKept);
        info.put("prediction_day_range", L.minDay + ".." + L.maxDay);
        info.put("prediction_header", L.header.toString());
        info.put("label_column_index", L.labelColumnIndex);
        info.put("extracted_column_indices", java.util.Arrays.toString(L.extractedColumnIndices));
        info.put("failures_loaded", failures.size());
        info.put("planned_jobs", plannedJobs);
        info.put("submission_cutoff_sec", HORIZON);
        info.put("nominal_utilization", rho);
        info.put("no_failures_mode", noFailures);
        info.put("workload_sha256", workloadHash);
        info.put("failures_sha256", failureHash);
        info.put("tier_timeline_sha256", tierHash);
        writeJson(new File(out, "inputs.json"), info);

        // ---------------------------------------------------------------- policies
        List<String[]> runs = new ArrayList<String[]>();      // {folder, kind, t0h}
        if (policySet.contains("E1")) {
            runs.add(new String[] {"E1_none", "E1", "0"});
        }
        for (String kind : new String[] {"E2", "E3"}) {
            if (policySet.contains(kind)) {
                for (String t : t0s) {
                    runs.add(new String[] {kind + (kind.equals("E2") ? "_fixed" : "_adaptive") + "_T0_" + t + "h",
                            kind, t});
                }
            }
        }
        SimParams p = SimParams.approved(HORIZON, perDc);
        StringBuilder res = new StringBuilder("run,wall_seconds,peak_heap_mb,cloudlets,load_seconds\n");
        for (String[] r : runs) {
            double t0h = Double.parseDouble(r[2]);
            CheckpointPolicy pol = r[1].equals("E1") ? Policies.none()
                    : r[1].equals("E2") ? Policies.fixed(t0h * 3600) : Policies.adaptive(t0h * 3600);
            File dir = new File(out, r[0]);
            resetPeaks();
            EventLog ev = new EventLog(dir);
            SimulationRunner.Result result;
            try {
                result = SimulationRunner.run(p, pol, streams, failures, failures.size() + 1, false, ev);
            } finally {
                ev.close();
            }
            writeJobs(new File(dir, "jobs.csv"), r[0], result.records, streams);
            writeHosts(new File(dir, "hosts.csv"), result, streams, failures);
            Map<String, Object> ri = new LinkedHashMap<String, Object>();
            ri.put("run", r[0]);
            ri.put("policy", pol.name());
            ri.put("t0_hours", t0h);
            ri.put("workload_sha256", workloadHash);
            ri.put("failures_sha256", failureHash);
            ri.put("tier_timeline_sha256", tierHash);
            ri.put("jobs_planned", plannedJobs);
            ri.put("jobs_submitted", result.records.size());
            ri.put("failures_scheduled", result.failuresScheduled);
            ri.put("failures_fired", result.failuresFired);
            ri.put("failures_applied", result.failuresApplied);
            ri.put("failures_while_idle_or_done", result.failuresWhileIdleOrDone);
            ri.put("cloudlets_submitted", result.cloudletsSubmitted);
            ri.put("sim_end_time", String.format(Locale.ROOT, "%.3f", result.simEndTime));
            writeJson(new File(dir, "run_info.json"), ri);
            res.append(r[0]).append(',').append(String.format(Locale.ROOT, "%.2f", result.wallMillis / 1000.0))
                    .append(',').append(peakHeapMb()).append(',').append(result.cloudletsSubmitted).append(',')
                    .append(String.format(Locale.ROOT, "%.2f", loadMs / 1000.0)).append('\n');
            System.out.printf(Locale.ROOT, "%-26s jobs=%d failures=%d/%d cloudlets=%d wall=%.1fs peakHeap=%dMB%n", r[0],
                    result.records.size(), result.failuresApplied, result.failuresFired, result.cloudletsSubmitted,
                    result.wallMillis / 1000.0, peakHeapMb());
        }
        writeText(new File(out, "resources.csv"), res.toString());
    }

    static String get(Map<String, String> m, String k, String d) {
        return m.containsKey(k) ? m.get(k) : d;
    }

    static String f(double v) {
        return Double.isNaN(v) ? "" : String.format(Locale.ROOT, "%.3f", v);
    }

    static void writeJobs(File file, String run, List<JobRecord> recs, List<StreamSpec> streams) throws IOException {
        StringBuilder b = new StringBuilder("run,job_id,stream,serial,job,length_sec,submit_time,start_time,"
                + "queue_delay_sec,finish_time,deadline,state,success,checkpoints,checkpoint_overhead_sec,"
                + "interrupted_write_sec,failures,lost_work_sec,recovery_sec,turnaround_sec,hosts_used\n");
        for (JobRecord j : recs) {
            StringBuilder hu = new StringBuilder();
            for (int h : j.hostsUsed) {
                hu.append(hu.length() == 0 ? "" : ";").append(h);
            }
            b.append(run).append(',').append(j.jobId).append(',').append(j.streamId).append(',')
                    .append(streams.get(j.streamId).label).append(',')
                    .append(j.jobIndex).append(',').append(f(j.lengthSec)).append(',').append(f(j.submitTime))
                    .append(',').append(f(j.startTime)).append(',').append(f(j.queueDelay())).append(',')
                    .append(f(j.finishTime)).append(',').append(f(j.deadline)).append(',').append(j.state())
                    .append(',').append(j.success() ? 1 : 0).append(',').append(j.checkpoints).append(',')
                    .append(f(j.checkpointOverheadSec)).append(',').append(f(j.lostCheckpointWriteSec)).append(',')
                    .append(j.failures).append(',').append(f(j.lostWorkSec)).append(',').append(f(j.recoverySec))
                    .append(',').append(f(j.turnaround())).append(',').append(hu).append('\n');
        }
        writeText(file, b.toString());
    }

    static void writeHosts(File file, SimulationRunner.Result r, List<StreamSpec> streams, List<FailureEvent> fails)
            throws IOException {
        Map<Integer, Double> ft = new HashMap<Integer, Double>();
        for (FailureEvent fe : fails) {
            ft.put(fe.streamId, fe.time);
        }
        int n = streams.size();
        int[] started = new int[n], succ = new int[n], ck = new int[n], fl = new int[n];
        double[] ov = new double[n], lost = new double[n], rec = new double[n], iw = new double[n], useful = new double[n];
        double[] qd = new double[n];
        for (JobRecord j : r.records) {
            int s = j.streamId;
            started[s]++;
            qd[s] += j.queueDelay();
            succ[s] += j.success() ? 1 : 0;
            ck[s] += j.checkpoints;
            fl[s] += j.failures;
            ov[s] += j.checkpointOverheadSec;
            lost[s] += j.lostWorkSec;
            rec[s] += j.recoverySec;
            iw[s] += j.lostCheckpointWriteSec;
            useful[s] += j.lengthSec;
        }
        StringBuilder b = new StringBuilder("stream,serial,primary_host_failed_flag,trace_failure_time,jobs_submitted,"
                + "jobs_successful,useful_work_sec,checkpoints,checkpoint_overhead_sec,interrupted_write_sec,failures,"
                + "lost_work_sec,recovery_sec,queue_delay_sec\n");
        for (int s = 0; s < n; s++) {
            b.append(s).append(',').append(streams.get(s).label).append(',')
                    .append(r.hostFailedFlag.get(s) ? 1 : 0).append(',')
                    .append(ft.containsKey(s) ? f(ft.get(s)) : "").append(',').append(started[s]).append(',')
                    .append(succ[s]).append(',').append(f(useful[s])).append(',').append(ck[s]).append(',')
                    .append(f(ov[s])).append(',').append(f(iw[s])).append(',').append(fl[s]).append(',')
                    .append(f(lost[s])).append(',').append(f(rec[s])).append(',').append(f(qd[s])).append('\n');
        }
        // spare hosts: index n.., must never be marked failed
        b.append("# spare hosts failed flags:");
        for (int h = n; h < r.hostFailedFlag.size(); h++) {
            b.append(' ').append(h).append('=').append(r.hostFailedFlag.get(h) ? 1 : 0);
        }
        b.append('\n');
        writeText(file, b.toString());
    }

    static void resetPeaks() {
        System.gc();
        for (MemoryPoolMXBean m : ManagementFactory.getMemoryPoolMXBeans()) {
            if (m.getType() == MemoryType.HEAP) {
                m.resetPeakUsage();
            }
        }
    }

    static long peakHeapMb() {
        long sum = 0;
        for (MemoryPoolMXBean m : ManagementFactory.getMemoryPoolMXBeans()) {
            if (m.getType() == MemoryType.HEAP) {
                sum += m.getPeakUsage().getUsed();
            }
        }
        return sum >> 20;
    }

    static void writeText(File f, String s) throws IOException {
        PrintWriter w = new PrintWriter(new OutputStreamWriter(new FileOutputStream(f), StandardCharsets.UTF_8));
        try {
            w.print(s);
        } finally {
            w.close();
        }
    }

    static void writeJson(File f, Map<String, Object> m) throws IOException {
        StringBuilder b = new StringBuilder("{\n");
        int i = 0;
        for (Map.Entry<String, Object> e : m.entrySet()) {
            Object v = e.getValue();
            String val = (v instanceof Number || v instanceof Boolean) ? String.valueOf(v)
                    : "\"" + String.valueOf(v).replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
            b.append("  \"").append(e.getKey()).append("\": ").append(val).append(++i < m.size() ? ",\n" : "\n");
        }
        writeText(f, b.append("}\n").toString());
    }
}
