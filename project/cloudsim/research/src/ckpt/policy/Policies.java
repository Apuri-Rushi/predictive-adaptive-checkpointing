package ckpt.policy;

/** The three approved experimental policies (E1, E2, E3). */
public final class Policies {
    /** Approved adaptive multipliers (Young/Daly ratios from validation tier failure rates). */
    public static final double LOW_MULTIPLIER = 2.65;
    public static final double HIGH_DIVISOR = 4.9;

    private Policies() {
    }

    /** E1: no checkpointing. */
    public static CheckpointPolicy none() {
        return new CheckpointPolicy() {
            public double intervalSeconds(RiskTier tier) {
                return Double.POSITIVE_INFINITY;
            }

            public String name() {
                return "E1_no_checkpoint";
            }
        };
    }

    /** E2: fixed interval T0 regardless of risk. */
    public static CheckpointPolicy fixed(final double t0Seconds) {
        checkPositive(t0Seconds);
        return new CheckpointPolicy() {
            public double intervalSeconds(RiskTier tier) {
                return t0Seconds;
            }

            public String name() {
                return "E2_fixed_T0=" + (t0Seconds / 3600.0) + "h";
            }
        };
    }

    /** E3: RF adaptive. LOW = 2.65 x T0, MEDIUM = T0, HIGH = T0 / 4.9. */
    public static CheckpointPolicy adaptive(final double t0Seconds) {
        checkPositive(t0Seconds);
        return new CheckpointPolicy() {
            public double intervalSeconds(RiskTier tier) {
                switch (tier) {
                    case LOW:
                        return LOW_MULTIPLIER * t0Seconds;
                    case HIGH:
                        return t0Seconds / HIGH_DIVISOR;
                    default:
                        return t0Seconds;
                }
            }

            public String name() {
                return "E3_adaptive_T0=" + (t0Seconds / 3600.0) + "h";
            }
        };
    }

    private static void checkPositive(double v) {
        if (!(v > 0) || Double.isInfinite(v)) {
            throw new IllegalArgumentException("interval must be positive and finite");
        }
    }
}
