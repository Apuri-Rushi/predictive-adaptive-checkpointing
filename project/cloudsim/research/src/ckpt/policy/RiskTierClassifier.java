package ckpt.policy;

/**
 * Maps a prior-corrected RF score to a tier.
 * Approved boundaries (validation 2019-05-11..05-24, internal model; NOT tuned on June data):
 *   LOW    : score <  0.000234   (validation P90)
 *   MEDIUM : 0.000234 <= score < 0.001732
 *   HIGH   : score >= 0.001732   (validation P99)
 */
public final class RiskTierClassifier {
    public static final double APPROVED_LOW_UPPER = 0.000234;
    public static final double APPROVED_HIGH_LOWER = 0.001732;

    private final double lowUpper;
    private final double highLower;

    public RiskTierClassifier(double lowUpper, double highLower) {
        if (!(lowUpper < highLower)) {
            throw new IllegalArgumentException("boundaries must satisfy lowUpper < highLower");
        }
        this.lowUpper = lowUpper;
        this.highLower = highLower;
    }

    public static RiskTierClassifier approved() {
        return new RiskTierClassifier(APPROVED_LOW_UPPER, APPROVED_HIGH_LOWER);
    }

    public RiskTier classify(double score) {
        if (Double.isNaN(score)) {
            throw new IllegalArgumentException("score is NaN");
        }
        if (score < lowUpper) {
            return RiskTier.LOW;
        }
        return score < highLower ? RiskTier.MEDIUM : RiskTier.HIGH;
    }
}
