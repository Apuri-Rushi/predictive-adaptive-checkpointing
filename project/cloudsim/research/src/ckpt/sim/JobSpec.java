package ckpt.sim;

/**
 * A predetermined job: identical for every policy (generated once, before any policy runs).
 * submitTime is the fixed arrival time; the job waits in its host's FIFO queue if the host is busy.
 */
public final class JobSpec {
    public final String jobId;        // e.g. "<serial>#<index>"
    public final int index;           // position in the stream
    public final double lengthSec;    // useful compute at full speed
    public final double submitTime;   // predetermined arrival time (simulation seconds)

    public JobSpec(String jobId, int index, double lengthSec, double submitTime) {
        this.jobId = jobId;
        this.index = index;
        this.lengthSec = lengthSec;
        this.submitTime = submitTime;
    }
}
