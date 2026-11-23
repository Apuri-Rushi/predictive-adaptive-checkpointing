package ckpt.risk;

import ckpt.policy.RiskTier;

/** The risk tier of a host as known at simulation time t (seconds; t = 0 is 2019-06-01 00:00). */
public interface RiskSource {
    RiskTier tierAt(double simTime);
}
