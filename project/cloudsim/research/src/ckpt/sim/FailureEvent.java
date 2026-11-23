package ckpt.sim;

/**
 * A simulated failure of the PRIMARY host of a stream at an absolute simulation time.
 * Only the FailureInjector consumes these; policies and the broker never see future failure times.
 */
public final class FailureEvent {
    public final int streamId;
    public final double time;

    public FailureEvent(int streamId, double time) {
        this.streamId = streamId;
        this.time = time;
    }
}
