package ckpt.sim;

import java.util.List;

import org.cloudbus.cloudsim.core.SimEntity;
import org.cloudbus.cloudsim.core.SimEvent;

/**
 * The ONLY component that knows trace failure times. At start it schedules one timer per
 * failure; when a timer fires it tells the broker "the primary host of stream s failed now".
 */
public final class FailureInjector extends SimEntity {
    private final List<FailureEvent> failures;
    private int brokerId = -1;
    private int fired;

    public FailureInjector(String name, List<FailureEvent> failures) {
        super(name);
        this.failures = failures;
    }

    public void setBrokerId(int brokerId) {
        this.brokerId = brokerId;
    }

    public int getFired() {
        return fired;
    }

    @Override
    public void startEntity() {
        if (brokerId < 0) {
            throw new IllegalStateException("broker id not set");
        }
        for (FailureEvent f : failures) {
            schedule(getId(), f.time, CkptTags.FAILURE_TIMER, f);   // delay from t = 0
        }
    }

    @Override
    public void processEvent(SimEvent ev) {
        if (ev.getTag() == CkptTags.FAILURE_TIMER) {
            FailureEvent f = (FailureEvent) ev.getData();
            fired++;
            sendNow(brokerId, CkptTags.HOST_FAILURE, Integer.valueOf(f.streamId));
        }
    }

    @Override
    public void shutdownEntity() {
    }
}
