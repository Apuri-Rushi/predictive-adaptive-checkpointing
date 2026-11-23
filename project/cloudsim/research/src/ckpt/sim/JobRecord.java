package ckpt.sim;

import java.util.ArrayList;
import java.util.List;

/** Per-job outcome and metric accumulators (all times in seconds). */
public final class JobRecord {
    public final int streamId;
    public final int jobIndex;
    public final String jobId;
    public final double lengthSec;
    public final double submitTime;      // predetermined arrival time
    public final double deadline;        // submitTime + factor * length
    public double startTime = Double.NaN;  // first time the job started executing
    public double finishTime = Double.NaN;
    public int checkpoints;              // completed checkpoints
    public double checkpointOverheadSec; // checkpoints * C (completed writes only)
    public double lostCheckpointWriteSec;// time spent on checkpoint writes interrupted by a failure
    public int failures;
    public double lostWorkSec;           // sum over failures of (progress at failure - committed work)
    public double recoverySec;           // sum over failures of D + B (+ R if a checkpoint existed)
    public final List<Integer> hostsUsed = new ArrayList<Integer>();  // host (= VM) indices, in order

    public JobRecord(int streamId, JobSpec spec, double deadlineFactor) {
        this.streamId = streamId;
        this.jobIndex = spec.index;
        this.jobId = spec.jobId;
        this.lengthSec = spec.lengthSec;
        this.submitTime = spec.submitTime;
        this.deadline = spec.submitTime + deadlineFactor * spec.lengthSec;
    }

    public boolean started() {
        return !Double.isNaN(startTime);
    }

    public boolean finished() {
        return !Double.isNaN(finishTime);
    }

    public boolean success() {
        return finished() && finishTime <= deadline + 1e-6;
    }

    /** Terminal state label: COMPLETED_ON_TIME, COMPLETED_LATE (deadline missed), or NOT_FINISHED. */
    public String state() {
        return !finished() ? "NOT_FINISHED" : success() ? "COMPLETED_ON_TIME" : "COMPLETED_LATE";
    }

    public double queueDelay() {
        return startTime - submitTime;
    }

    public double turnaround() {
        return finishTime - submitTime;
    }
}
