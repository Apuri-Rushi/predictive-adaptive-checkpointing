package ckpt.app;

import java.util.ArrayList;
import java.util.List;

import ckpt.policy.Policies;
import ckpt.risk.ConstantRisk;
import ckpt.sim.FailureEvent;
import ckpt.sim.SimParams;
import ckpt.sim.SimulationRunner;
import ckpt.sim.StreamSpec;

/**
 * SYNTHETIC scale benchmark (no trace data): N streams over a 30-day horizon with the approved job mix
 * (24/72/168 h by a fixed rotation), fixed T0 = 1 h (the densest checkpointing in the sweep),
 * ~0.16 % of hosts failing at spread-out times. Measures runtime and memory to size the pilot shard.
 * Usage: java ... ckpt.app.ScaleBenchmark <streams> <hostsPerDatacenter>
 */
public class ScaleBenchmark {
    public static void main(String[] args) throws Exception {
        int n = Integer.parseInt(args[0]);
        int perDc = Integer.parseInt(args[1]);
        double h = 3600, day = 86400;
        List<StreamSpec> ss = new ArrayList<StreamSpec>();
        for (int s = 0; s < n; s++) {
            ss.add(new StreamSpec(s, "syn" + s, ckpt.trace.WorkloadGenerator.plan("syn" + s, 0.0, 30 * day),
                    ConstantRisk.MEDIUM));
        }
        List<FailureEvent> fe = new ArrayList<FailureEvent>();
        int nf = Math.max(1, n * 16 / 10000);
        for (int k = 0; k < nf; k++) {
            fe.add(new FailureEvent((int) ((long) k * 7919 % n), day * (1 + 28.0 * k / nf) + 3600 * (k % 24)));
        }
        Runtime rt = Runtime.getRuntime();
        System.gc();
        SimulationRunner.Result r = SimulationRunner.run(SimParams.approved(30 * day, perDc), Policies.fixed(h),
                ss, fe, nf + 1, false);
        long used = (rt.totalMemory() - rt.freeMemory()) / (1 << 20);
        System.out.printf("streams=%d hostsPerDC=%d jobs=%d cloudlets=%d failures=%d/%d wall=%.1fs heapUsed~%dMB maxHeap=%dMB simEnd=%.0fs%n",
                n, perDc, r.records.size(), r.cloudletsSubmitted, r.failuresApplied, r.failuresFired,
                r.wallMillis / 1000.0, used, rt.maxMemory() / (1 << 20), r.simEndTime);
    }
}
