package ckpt.trace;

import java.util.ArrayList;
import java.util.List;

import ckpt.sim.JobSpec;

/**
 * Predetermined, policy-independent workload (generated ONCE per shard, before any policy runs).
 *
 * Job mix (approved): job j of drive s has length
 *     crc32(serial + "|" + j) % 10 :  0-4 -> 24 h,  5-7 -> 72 h,  8-9 -> 168 h   (p = 0.5 / 0.3 / 0.2).
 * Submit times: nominal back-to-back arrivals from the host's first day,
 *     submit_0 = start,  submit_{j+1} = submit_j + L_j,
 * i.e. the times at which each job would arrive if every previous job ran with no overhead and no failure.
 * Jobs are generated while submit_j < cutoff (common 30-day cutoff). Under any policy with overhead or
 * failures, a job that arrives while its host is busy waits in that host's FIFO queue.
 */
public final class WorkloadGenerator {
    private static final double H = 3600.0;

    private WorkloadGenerator() {
    }

    public static double length(String serial, int j) {
        long v = Hashing.crc32(serial + "|" + j) % 10;
        return v <= 4 ? 24 * H : v <= 7 ? 72 * H : 168 * H;
    }

    public static List<JobSpec> plan(String serial, double startTime, double cutoff) {
        return plan(serial, startTime, cutoff, 1.0);
    }

    /**
     * Same, with nominal utilisation rho in (0, 1]: submit_{j+1} = submit_j + L_j / rho.
     * rho = 1.0 is the default (nominal back-to-back). rho < 1 leaves idle slack between nominal jobs;
     * it is a SENSITIVITY option only, pending approval.
     */
    public static List<JobSpec> plan(String serial, double startTime, double cutoff, double rho) {
        if (!(rho > 0 && rho <= 1)) {
            throw new IllegalArgumentException("utilisation must be in (0, 1]");
        }
        List<JobSpec> out = new ArrayList<JobSpec>();
        double t = startTime;
        for (int j = 0; t < cutoff; j++) {
            double L = length(serial, j);
            out.add(new JobSpec(serial + "#" + j, j, L, t));
            t += L / rho;
        }
        return out;
    }
}
