package ckpt.sim;

/** Simulation constants. Times in seconds; 0 = 2019-06-01 00:00. */
public final class SimParams {
    public final double mips;               // per-PE speed of every host/VM
    public final double checkpointSec;      // C: checkpoint save time
    public final double restoreSec;         // R: restore time (only if a checkpoint exists)
    public final double detectSec;          // D: failure-detection delay
    public final double bootSec;            // B: replacement host boot time
    public final double deadlineFactor;     // deadline = submit + factor * length
    public final double horizonSec;         // no NEW job is started at or after this time
    public final int hostsPerDatacenter;    // grouping of hosts into datacenter entities (performance)

    public SimParams(double mips, double checkpointSec, double restoreSec, double detectSec, double bootSec,
                     double deadlineFactor, double horizonSec, int hostsPerDatacenter) {
        this.mips = mips;
        this.checkpointSec = checkpointSec;
        this.restoreSec = restoreSec;
        this.detectSec = detectSec;
        this.bootSec = bootSec;
        this.deadlineFactor = deadlineFactor;
        this.horizonSec = horizonSec;
        this.hostsPerDatacenter = hostsPerDatacenter;
    }

    /** Approved Phase-3 values: C = R = 300 s, D = 60 s, B = 120 s, deadline 1.5 x L, 1000 MIPS. */
    public static SimParams approved(double horizonSec, int hostsPerDatacenter) {
        return new SimParams(1000.0, 300.0, 300.0, 60.0, 120.0, 1.5, horizonSec, hostsPerDatacenter);
    }
}
