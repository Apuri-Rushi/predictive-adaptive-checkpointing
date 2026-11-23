package ckpt.risk;

import java.util.Map;
import java.util.TreeMap;

import ckpt.policy.RiskTier;
import ckpt.policy.RiskTierClassifier;

/**
 * Daily RF scores of one host, with the two approved availability rules:
 *  1. a score for prediction day d (day index, 0 = 2019-06-01) becomes effective at 00:00 of day d+1;
 *  2. a day without a new score keeps the most recent available score (carry-forward).
 * Before any score is effective, the host is MEDIUM.
 * Only scores are stored here - never labels or failure information.
 */
public final class DailyScoreTimeline implements RiskSource {
    public static final double DAY = 86400.0;

    private final TreeMap<Integer, Double> scoreByDay = new TreeMap<Integer, Double>();
    private final RiskTierClassifier classifier;

    public DailyScoreTimeline(RiskTierClassifier classifier) {
        this.classifier = classifier;
    }

    /** dayIndex = prediction date - 2019-06-01 in days (may be negative for earlier dates). */
    public void addScore(int dayIndex, double score) {
        if (scoreByDay.put(dayIndex, score) != null) {
            throw new IllegalStateException("duplicate score for day " + dayIndex);
        }
    }

    /** Score in force at simTime, or NaN if none yet. */
    public double scoreAt(double simTime) {
        int currentDay = (int) Math.floor(simTime / DAY);
        // effective scores are those with predictionDay + 1 <= currentDay
        Map.Entry<Integer, Double> e = scoreByDay.floorEntry(currentDay - 1);
        return e == null ? Double.NaN : e.getValue();
    }

    public RiskTier tierAt(double simTime) {
        double s = scoreAt(simTime);
        return Double.isNaN(s) ? RiskTier.MEDIUM : classifier.classify(s);
    }

    public int size() {
        return scoreByDay.size();
    }
}
