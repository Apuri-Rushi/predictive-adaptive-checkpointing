package ckpt;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import ckpt.policy.CheckpointPolicy;
import ckpt.policy.Policies;
import ckpt.policy.RiskTier;
import ckpt.policy.RiskTierClassifier;
import ckpt.risk.ConstantRisk;
import ckpt.risk.DailyScoreTimeline;
import ckpt.risk.RiskSource;
import ckpt.sim.FailureEvent;
import ckpt.sim.JobRecord;
import ckpt.sim.JobSpec;
import ckpt.sim.SimParams;
import ckpt.sim.SimulationRunner;
import ckpt.sim.SimulationRunner.Result;
import ckpt.sim.StreamSpec;

/**
 * Hand-computed scenario tests for the checkpoint / failure / recovery mechanism.
 * Approved parameters: C = R = 300 s, D = 60 s, B = 120 s, deadline = 1.5 x L, 1000 MIPS.
 * Job L = 24 h = 86,400 s unless stated. Fixed policy T0 = 4 h = 14,400 s.
 * CloudSim adds a ~0.2 s start-up offset and <= ~0.1 s per cloudlet, hence the time tolerance.
 * Run: java ... ckpt.ScenarioTests
 */
public final class ScenarioTests {
    static final double H = 3600.0;
    static final double L = 24 * H;
    static final double T0 = 4 * H;
    static final double TOL_T = 10.0;   // seconds, for event times
    static int passed, failed;
    static final List<String> failures = new ArrayList<String>();

    public static void main(String[] args) throws Exception {
        long t = System.currentTimeMillis();
        s1NormalCompletion();
        s2CheckpointThenFailure();
        s3RecoveryFromLatestCheckpoint();
        s4ResumeOnReplacementHost();
        s5FailureBeforeFirstCheckpoint();
        s6DeadlineMiss();
        x1FailureDuringCheckpointWrite();
        x2AdaptiveIntervalsByTier();
        x3DailyTimelineRules();
        x4TierChangeAtMidnight();
        x5MultiStreamMultiDatacenter();
        w1QueueingBehindOverhead();
        w2DeadlineMissCausedByQueueing();
        w3FailureWhileIdle();
        w4ArrivalDuringIdleRecovery();
        w5IdenticalJobSetAcrossPolicies();
        System.out.println();
        System.out.println("==== " + passed + " checks passed, " + failed + " failed  ("
                + (System.currentTimeMillis() - t) + " ms) ====");
        for (String f : failures) {
            System.out.println("FAILED: " + f);
        }
        System.exit(failed == 0 ? 0 : 1);
    }

    // ------------------------------------------------------------------ helpers
    static SimParams params() {
        return SimParams.approved(30 * 86400.0, 10);
    }

    static List<StreamSpec> oneStream(double length, RiskSource risk) {
        return Collections.singletonList(new StreamSpec(0, "test-drive",
                Arrays.asList(new JobSpec("t#0", 0, length, 0.0)), risk));
    }

    /** One stream with predetermined (length, submit) pairs. */
    static List<StreamSpec> streamOf(RiskSource risk, double... lengthSubmitPairs) {
        List<JobSpec> js = new ArrayList<JobSpec>();
        for (int i = 0; i < lengthSubmitPairs.length; i += 2) {
            js.add(new JobSpec("t#" + i / 2, i / 2, lengthSubmitPairs[i], lengthSubmitPairs[i + 1]));
        }
        return Collections.singletonList(new StreamSpec(0, "test-drive", js, risk));
    }

    static Result run(CheckpointPolicy pol, List<StreamSpec> streams, List<FailureEvent> fails, int spares)
            throws Exception {
        return SimulationRunner.run(params(), pol, streams, fails, spares, true);
    }

    static List<FailureEvent> failAt(double t) {
        return Collections.singletonList(new FailureEvent(0, t));
    }

    static void near(String name, double got, double exp, double tol) {
        boolean ok = Math.abs(got - exp) <= tol;
        report(name + String.format(" = %.2f (expected %.2f +/- %.1f)", got, exp, tol), ok);
    }

    static void eq(String name, Object got, Object exp) {
        report(name + " = " + got + " (expected " + exp + ")", got.equals(exp));
    }

    static void check(String name, boolean ok) {
        report(name, ok);
    }

    static void report(String s, boolean ok) {
        System.out.println((ok ? "  [PASS] " : "  [FAIL] ") + s);
        if (ok) {
            passed++;
        } else {
            failed++;
            failures.add(s);
        }
    }

    static void header(String s) {
        System.out.println();
        System.out.println("## " + s);
    }

    static boolean traceHas(Result r, String fragment) {
        for (String line : r.trace) {
            if (line.contains(fragment)) {
                return true;
            }
        }
        return false;
    }

    static double firstTraceTime(Result r, String fragment) {
        for (String line : r.trace) {
            if (line.contains(fragment)) {
                return Double.parseDouble(line.trim().split("\\s+")[0]);
            }
        }
        return Double.NaN;
    }

    // ------------------------------------------------------------------ required scenarios
    /** S1: no failure, fixed 4 h: 6 segments, 5 checkpoints, finish = L + 5C = 87,900 s. */
    static void s1NormalCompletion() throws Exception {
        header("S1 normal task completion (fixed T0 = 4 h, no failure)");
        Result r = run(Policies.fixed(T0), oneStream(L, ConstantRisk.MEDIUM), new ArrayList<FailureEvent>(), 1);
        JobRecord j = r.records.get(0);
        check("job finished", j.finished());
        near("finish time", j.finishTime, L + 5 * 300, TOL_T);
        eq("checkpoints", j.checkpoints, 5);
        near("checkpoint overhead", j.checkpointOverheadSec, 1500, 1e-9);
        eq("failures", j.failures, 0);
        near("lost work", j.lostWorkSec, 0, 1e-9);
        check("deadline met (success)", j.success());
        eq("hosts used", j.hostsUsed, Arrays.asList(0));
    }

    /** S2: failure at t = 36,000 s, after 2 checkpoints (committed 28,800 s): lost = 6,600 s. */
    static void s2CheckpointThenFailure() throws Exception {
        header("S2 checkpoint followed by failure (failure at 10 h)");
        Result r = run(Policies.fixed(T0), oneStream(L, ConstantRisk.MEDIUM), failAt(36000), 1);
        JobRecord j = r.records.get(0);
        check("2 checkpoints committed before the failure",
                traceHas(r, "checkpoint committed=14400.0") && traceHas(r, "checkpoint committed=28800.0")
                        && firstTraceTime(r, "HOST FAILURE") > firstTraceTime(r, "checkpoint committed=28800.0"));
        check("failure reports committed work 28,800 s", traceHas(r, "committed=28800.0 lost="));
        eq("failures", j.failures, 1);
        near("lost work", j.lostWorkSec, 36000 - 29400, TOL_T);
        eq("failures applied by broker", r.failuresApplied, 1);
    }

    /** S3: recovery: ready at 36,180, restore to 36,480, remaining 57,600 s with 3 more checkpoints:
     *  finish = 36,480 + 57,600 + 3 x 300 = 94,980 s. */
    static void s3RecoveryFromLatestCheckpoint() throws Exception {
        header("S3 recovery from latest checkpoint");
        Result r = run(Policies.fixed(T0), oneStream(L, ConstantRisk.MEDIUM), failAt(36000), 1);
        JobRecord j = r.records.get(0);
        near("restore completes at", firstTraceTime(r, "restored committed=28800.0"), 36000 + 60 + 120 + 300, TOL_T);
        near("recovery time (D + B + R)", j.recoverySec, 480, 1e-9);
        near("finish time", j.finishTime, 94980, TOL_T);
        eq("total checkpoints (2 before + 3 after)", j.checkpoints, 5);
        check("job still meets deadline 129,600 s", j.success());
    }

    /** S4: after the failure the job continues on the spare host; failed host is marked failed. */
    static void s4ResumeOnReplacementHost() throws Exception {
        header("S4 resume on replacement host");
        Result r = run(Policies.fixed(T0), oneStream(L, ConstantRisk.MEDIUM), failAt(36000), 1);
        JobRecord j = r.records.get(0);
        eq("hosts used (primary 0 -> spare 1)", j.hostsUsed, Arrays.asList(0, 1));
        eq("primary host 0 isFailed", r.hostFailedFlag.get(0), Boolean.TRUE);
        eq("spare host 1 isFailed", r.hostFailedFlag.get(1), Boolean.FALSE);
        check("restore ran on vm 1", traceHas(r, "restored committed=28800.0 on vm 1"));
        check("job completed after moving", j.finished());
    }

    /** S5: failure at 2 h before any checkpoint: lost 7,200 s, restart from zero, no restore:
     *  finish = 7,200 + 180 + 86,400 + 5 x 300 = 95,280 s. */
    static void s5FailureBeforeFirstCheckpoint() throws Exception {
        header("S5 failure before first checkpoint (failure at 2 h)");
        Result r = run(Policies.fixed(T0), oneStream(L, ConstantRisk.MEDIUM), failAt(7200), 1);
        JobRecord j = r.records.get(0);
        near("lost work", j.lostWorkSec, 7200, TOL_T);
        near("recovery time (D + B, no restore)", j.recoverySec, 180, 1e-9);
        check("restarted from zero", traceHas(r, "restart from zero on vm 1"));
        near("finish time", j.finishTime, 95280, TOL_T);
        eq("checkpoints (all after restart)", j.checkpoints, 5);
        check("deadline met", j.success());
    }

    /** S6: no checkpointing, failure at 23 h: restart from zero, finish 169,380 > deadline 129,600. */
    static void s6DeadlineMiss() throws Exception {
        header("S6 deadline miss (no checkpointing, failure at 23 h)");
        Result r = run(Policies.none(), oneStream(L, ConstantRisk.MEDIUM), failAt(23 * H), 1);
        JobRecord j = r.records.get(0);
        near("lost work", j.lostWorkSec, 23 * H, TOL_T);
        near("finish time", j.finishTime, 23 * H + 180 + L, TOL_T);
        near("deadline", j.deadline, 1.5 * L, 1.0);
        check("deadline MISSED (success = false)", !j.success());
        eq("checkpoints", j.checkpoints, 0);
    }

    // ------------------------------------------------------------------ additional checks
    /** Failure during the first checkpoint write (t = 14,550 s): checkpoint lost, restart from zero. */
    static void x1FailureDuringCheckpointWrite() throws Exception {
        header("X1 failure during checkpoint write (t = 14,550 s)");
        Result r = run(Policies.fixed(T0), oneStream(L, ConstantRisk.MEDIUM), failAt(14550), 1);
        JobRecord j = r.records.get(0);
        near("lost work (segment not committed)", j.lostWorkSec, 14400, TOL_T);
        near("interrupted checkpoint write time", j.lostCheckpointWriteSec, 150, TOL_T);
        near("recovery (no checkpoint existed)", j.recoverySec, 180, 1e-9);
        near("finish time", j.finishTime, 14550 + 180 + L + 5 * 300, TOL_T);
    }

    /** Adaptive policy with a constant tier. HIGH: T = 14,400/4.9 = 2,938.8 s -> 30 segments, 29 ckpts.
     *  LOW: T = 2.65 x 14,400 = 38,160 s -> 3 segments, 2 ckpts. MEDIUM equals fixed. NONE: no ckpts. */
    static void x2AdaptiveIntervalsByTier() throws Exception {
        header("X2 adaptive intervals by tier (no failure)");
        JobRecord hi = run(Policies.adaptive(T0), oneStream(L, new ConstantRisk(RiskTier.HIGH)),
                new ArrayList<FailureEvent>(), 1).records.get(0);
        eq("HIGH: checkpoints", hi.checkpoints, 29);
        near("HIGH: finish", hi.finishTime, L + 29 * 300, TOL_T);
        JobRecord lo = run(Policies.adaptive(T0), oneStream(L, new ConstantRisk(RiskTier.LOW)),
                new ArrayList<FailureEvent>(), 1).records.get(0);
        eq("LOW: checkpoints", lo.checkpoints, 2);
        near("LOW: finish", lo.finishTime, L + 2 * 300, TOL_T);
        JobRecord me = run(Policies.adaptive(T0), oneStream(L, ConstantRisk.MEDIUM),
                new ArrayList<FailureEvent>(), 1).records.get(0);
        eq("MEDIUM: checkpoints (= fixed)", me.checkpoints, 5);
        JobRecord no = run(Policies.none(), oneStream(L, ConstantRisk.MEDIUM),
                new ArrayList<FailureEvent>(), 1).records.get(0);
        eq("NONE: checkpoints", no.checkpoints, 0);
        near("NONE: finish", no.finishTime, L, TOL_T);
    }

    /** Score of day d is effective from 00:00 of day d+1; missing days carry the last score forward. */
    static void x3DailyTimelineRules() {
        header("X3 daily score timeline: d+1 availability and carry-forward");
        DailyScoreTimeline tl = new DailyScoreTimeline(RiskTierClassifier.approved());
        tl.addScore(0, 0.0001);   // LOW, effective from day 1
        tl.addScore(2, 0.005);    // HIGH, effective from day 3 (day 1 has no score -> carry forward)
        double D = 86400;
        eq("day 0 (no score effective yet) -> MEDIUM", tl.tierAt(0.5 * D), RiskTier.MEDIUM);
        eq("day 1 -> LOW (score of day 0)", tl.tierAt(1.0 * D), RiskTier.LOW);
        eq("day 2 -> LOW (carried forward; day 1 missing)", tl.tierAt(2.99 * D), RiskTier.LOW);
        eq("day 3 00:00 -> HIGH (score of day 2)", tl.tierAt(3.0 * D), RiskTier.HIGH);
        eq("day 20 -> HIGH (carried forward)", tl.tierAt(20.5 * D), RiskTier.HIGH);
        RiskTierClassifier c = RiskTierClassifier.approved();
        eq("boundary 0.000234 -> MEDIUM", c.classify(0.000234), RiskTier.MEDIUM);
        eq("boundary 0.001732 -> HIGH", c.classify(0.001732), RiskTier.HIGH);
        eq("0.0002339 -> LOW", c.classify(0.0002339), RiskTier.LOW);
    }

    /** LOW on day 0, HIGH from day 1 00:00. Low checkpoints at ~38,460 and ~76,920; at midnight
     *  (86,400) the HIGH interval (2,938.8 s) is already overdue -> immediate checkpoint done ~86,700. */
    static void x4TierChangeAtMidnight() throws Exception {
        header("X4 tier change at midnight (adaptive)");
        DailyScoreTimeline tl = new DailyScoreTimeline(RiskTierClassifier.approved());
        tl.addScore(-1, 0.0001);   // effective day 0 -> LOW
        tl.addScore(0, 0.01);      // effective day 1 -> HIGH
        Result r = run(Policies.adaptive(T0), oneStream(72 * H, tl), new ArrayList<FailureEvent>(), 1);
        List<Double> ck = new ArrayList<Double>();
        for (String line : r.trace) {
            if (line.contains("checkpoint committed")) {
                ck.add(Double.parseDouble(line.trim().split("\\s+")[0]));
            }
        }
        near("1st checkpoint (LOW)", ck.get(0), 38160 + 300, TOL_T);
        near("2nd checkpoint (LOW)", ck.get(1), 2 * 38460, TOL_T);
        near("3rd checkpoint (overdue at midnight, HIGH)", ck.get(2), 86400 + 300, TOL_T);
        near("4th checkpoint spacing (HIGH)", ck.get(3) - ck.get(2), 14400 / 4.9 + 300, TOL_T);
        check("job finished", r.records.get(0).finished());
    }

    /** 3 streams in 2 datacenters; streams 0 and 2 fail and move to distinct spares; stream 1 untouched. */
    static void x5MultiStreamMultiDatacenter() throws Exception {
        header("X5 multiple streams / datacenters / spares");
        SimParams p = SimParams.approved(30 * 86400.0, 2);   // 2 hosts per datacenter -> 3 datacenters
        List<StreamSpec> ss = new ArrayList<StreamSpec>();
        for (int s = 0; s < 3; s++) {
            ss.add(new StreamSpec(s, "d" + s, Arrays.asList(new JobSpec("d" + s + "#0", 0, L, 0.0),
                    new JobSpec("d" + s + "#1", 1, L, L)), ConstantRisk.MEDIUM));
        }
        List<FailureEvent> fe = Arrays.asList(new FailureEvent(0, 36000), new FailureEvent(2, 100000));
        Result r = SimulationRunner.run(p, Policies.fixed(T0), ss, fe, 2, true);
        eq("jobs recorded", r.records.size(), 6);
        int done = 0;
        for (JobRecord j : r.records) {
            done += j.finished() ? 1 : 0;
        }
        eq("jobs finished", done, 6);
        eq("failures fired / applied", r.failuresFired + "/" + r.failuresApplied, "2/2");
        JobRecord s0 = null, s2 = null, s1a = null;
        for (JobRecord j : r.records) {
            if (j.streamId == 0 && j.jobIndex == 0) s0 = j;
            if (j.streamId == 2 && j.jobIndex == 1) s2 = j;
            if (j.streamId == 1 && j.jobIndex == 0) s1a = j;
        }
        eq("stream 0 hosts", s0.hostsUsed, Arrays.asList(0, 3));
        eq("stream 2 second job hosts", s2.hostsUsed, Arrays.asList(2, 4));
        eq("stream 1 unaffected: failures", s1a.failures, 0);
        near("stream 1 job 0 finish", s1a.finishTime, L + 1500, TOL_T);
    }

    // ------------------------------------------------------------------ predetermined workload / queueing
    /** Two 24 h jobs submitted at 0 and 86,400 (nominal back-to-back). Fixed 4 h: job 0 finishes at 87,900,
     *  so job 1 waits 1,500 s, starts 87,900 and finishes 175,800; turnaround 89,400; deadline 216,000 met. */
    static void w1QueueingBehindOverhead() throws Exception {
        header("W1 predetermined arrivals: queueing behind checkpoint overhead");
        Result r = run(Policies.fixed(T0), streamOf(ConstantRisk.MEDIUM, L, 0, L, L), new ArrayList<FailureEvent>(), 1);
        JobRecord j0 = r.records.get(0), j1 = r.records.get(1);
        near("job 1 submit (predetermined)", j1.submitTime, L, 1e-9);
        near("job 1 queue delay", j1.queueDelay(), 1500, TOL_T);
        near("job 1 finish", j1.finishTime, 175800, TOL_T);
        near("job 1 turnaround (incl. queueing)", j1.turnaround(), 89400, TOL_T);
        near("job 1 deadline = submit + 1.5 L", j1.deadline, L + 1.5 * L, 1e-9);
        check("both on time", j0.success() && j1.success());
        eq("job 1 state", j1.state(), "COMPLETED_ON_TIME");
    }

    /** No checkpointing, failure at 23 h during job 0: job 0 finishes 169,380 (late). Job 1 (submitted 86,400)
     *  waits until 169,380, finishes 255,780 > deadline 216,000 -> late too. Nothing is skipped. */
    static void w2DeadlineMissCausedByQueueing() throws Exception {
        header("W2 deadline miss caused by queueing (no checkpointing, failure at 23 h)");
        Result r = run(Policies.none(), streamOf(ConstantRisk.MEDIUM, L, 0, L, L), failAt(23 * H), 1);
        JobRecord j0 = r.records.get(0), j1 = r.records.get(1);
        eq("jobs submitted", r.records.size(), 2);
        near("job 1 queue delay", j1.queueDelay(), 169380 - L, TOL_T);
        near("job 1 finish", j1.finishTime, 255780, TOL_T);
        eq("job 0 state", j0.state(), "COMPLETED_LATE");
        eq("job 1 state", j1.state(), "COMPLETED_LATE");
        eq("job 1 failures (it never ran on the failed host)", j1.failures, 0);
        eq("job 1 hosts used", j1.hostsUsed, Arrays.asList(1));
    }

    /** Failure at 150,000 s while the host is idle (job 0 done at 86,400, job 1 arrives at 200,000):
     *  no work lost; replacement ready at 150,180; job 1 runs on the spare with no queueing. */
    static void w3FailureWhileIdle() throws Exception {
        header("W3 host failure while idle");
        Result r = run(Policies.fixed(T0), streamOf(ConstantRisk.MEDIUM, 3600, 0, 3600, 200000), failAt(150000), 1);
        JobRecord j1 = r.records.get(1);
        eq("failures applied to running work", r.failuresApplied, 0);
        eq("job 1 failures", j1.failures, 0);
        near("job 1 lost work", j1.lostWorkSec, 0, 1e-9);
        eq("job 1 hosts used (spare only)", j1.hostsUsed, Arrays.asList(1));
        near("job 1 queue delay", j1.queueDelay(), 0, TOL_T);
        eq("primary host 0 isFailed", r.hostFailedFlag.get(0), Boolean.TRUE);
    }

    /** Failure at 199,950 s while idle; job 1 arrives at 200,000 but the replacement is ready only at
     *  199,950 + 180 = 200,130 -> job 1 waits 130 s. */
    static void w4ArrivalDuringIdleRecovery() throws Exception {
        header("W4 arrival while the replacement host is still booting");
        Result r = run(Policies.fixed(T0), streamOf(ConstantRisk.MEDIUM, 3600, 0, 3600, 200000), failAt(199950), 1);
        JobRecord j1 = r.records.get(1);
        near("job 1 start", j1.startTime, 200130, TOL_T);
        near("job 1 queue delay", j1.queueDelay(), 130, TOL_T);
        eq("job 1 hosts used", j1.hostsUsed, Arrays.asList(1));
    }

    /** Same predetermined workload under E1 / E2 / E3 with one failure: identical job ids, lengths, submit
     *  times and primary host for every policy; every job reaches a terminal state. */
    static void w5IdenticalJobSetAcrossPolicies() throws Exception {
        header("W5 identical job set across policies");
        List<StreamSpec> ss = new ArrayList<StreamSpec>();
        for (int s = 0; s < 4; s++) {
            ss.add(new StreamSpec(s, "w" + s, ckpt.trace.WorkloadGenerator.plan("w" + s, 0.0, 10 * 86400.0),
                    s == 1 ? new ConstantRisk(RiskTier.HIGH) : ConstantRisk.MEDIUM));
        }
        List<FailureEvent> fe = Arrays.asList(new FailureEvent(1, 300000));
        String ref = null;
        boolean same = true, terminal = true;
        for (CheckpointPolicy pol : Arrays.asList(Policies.none(), Policies.fixed(T0), Policies.adaptive(T0))) {
            Result r = SimulationRunner.run(SimParams.approved(30 * 86400.0, 2), pol, ss, fe, 1, false);
            StringBuilder b = new StringBuilder();
            List<JobRecord> recs = new ArrayList<JobRecord>(r.records);
            java.util.Collections.sort(recs, new java.util.Comparator<JobRecord>() {
                public int compare(JobRecord a, JobRecord c) {
                    return a.jobId.compareTo(c.jobId);
                }
            });
            for (JobRecord j : recs) {
                b.append(j.jobId).append('|').append(j.lengthSec).append('|').append(j.submitTime).append('|')
                        .append(j.streamId).append('\n');      // assigned (primary) host = stream
                terminal &= j.finished();
            }
            if (ref == null) {
                ref = b.toString();
            } else {
                same &= ref.equals(b.toString());
            }
        }
        check("identical job ids / lengths / submit times / host assignment for E1, E2, E3", same);
        check("every job reached a terminal state under every policy", terminal);
    }
}
