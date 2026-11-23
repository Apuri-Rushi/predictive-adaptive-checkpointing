package ckpt.risk;

import ckpt.policy.RiskTier;

/** Fixed tier. Used for replacement (spare) hosts, which use MEDIUM by approved assumption. */
public final class ConstantRisk implements RiskSource {
    public static final ConstantRisk MEDIUM = new ConstantRisk(RiskTier.MEDIUM);

    private final RiskTier tier;

    public ConstantRisk(RiskTier tier) {
        this.tier = tier;
    }

    public RiskTier tierAt(double simTime) {
        return tier;
    }
}
