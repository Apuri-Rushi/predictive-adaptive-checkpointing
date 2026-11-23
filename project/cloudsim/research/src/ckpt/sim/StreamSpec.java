package ckpt.sim;

import java.util.Collections;
import java.util.List;

import ckpt.risk.RiskSource;

/**
 * One work stream = the predetermined jobs assigned to one trace host (one Backblaze drive).
 * Jobs arrive at fixed submit times and are served FIFO, one at a time, by the stream's current
 * host (its primary host until that host fails, then a spare host). The job list is generated once
 * and shared by every policy, so job IDs, lengths, submit times and host assignment are identical.
 */
public final class StreamSpec {
    public final int streamId;
    public final String label;                 // drive serial number (identifier only)
    public final List<JobSpec> jobs;           // ordered by submitTime
    public final RiskSource risk;              // risk of the PRIMARY host (spares use MEDIUM)

    public StreamSpec(int streamId, String label, List<JobSpec> jobs, RiskSource risk) {
        for (int i = 1; i < jobs.size(); i++) {
            if (jobs.get(i).submitTime < jobs.get(i - 1).submitTime) {
                throw new IllegalArgumentException("jobs must be ordered by submit time");
            }
        }
        this.streamId = streamId;
        this.label = label;
        this.jobs = Collections.unmodifiableList(jobs);
        this.risk = risk;
    }
}
