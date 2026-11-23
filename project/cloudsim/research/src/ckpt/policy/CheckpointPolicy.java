package ckpt.policy;

/**
 * Decides the checkpoint interval (seconds of wall-clock time since the last completed checkpoint,
 * or since the (re)start of the job) for a host currently in the given risk tier.
 * Return Double.POSITIVE_INFINITY for "never checkpoint".
 */
public interface CheckpointPolicy {
    double intervalSeconds(RiskTier tier);

    String name();
}
