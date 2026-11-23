package ckpt.sim;

/** Custom event tags (far above CloudSimTags values). */
public final class CkptTags {
    public static final int HOST_FAILURE = 910001;      // injector -> broker, data = Integer streamId
    public static final int RECOVERY_READY = 910002;    // broker -> broker, data = Integer streamId
    public static final int FAILURE_TIMER = 910003;     // injector -> injector, data = FailureEvent

    private CkptTags() {
    }
}
