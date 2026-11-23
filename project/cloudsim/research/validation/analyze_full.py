#!/usr/bin/env python
"""
Statistical analysis of one complete utilisation scenario (results/full_rho<ρ>/).

Unit of analysis: the HOST (one drive = one work stream with its predetermined jobs). Shards are only
partitions of the host population and are never treated as samples.

Point estimates are population ratios over all hosts (e.g. late jobs / jobs, overhead h / useful h).
Uncertainty: paired, host-clustered Poisson bootstrap (B = 2000, fixed seed). In every replicate each host
gets one weight w ~ Poisson(1) that is applied to BOTH policies of a comparison, so differences are paired
on identical hosts and jobs. Strata (failing / non-failing hosts) are bootstrapped separately.
95 % percentile intervals are reported; no significance testing / no multiplicity correction is claimed.

Outputs in <run>/analysis/:
  host_metrics.parquet-free CSVs:  policy_summary.csv, paired_comparisons.csv, tier_breakdown.csv,
  tier_occupancy.csv, checkpoints_by_tier.csv, failures_detail.csv, analysis_meta.json
Usage: python -I research/validation/analyze_full.py results/full_rho0.9 [--boot 2000] [--workers 3]
"""
import argparse
import concurrent.futures as cf
import json
import os

import numpy as np
import pandas as pd

RUNS = ["E1_none"] + [f"E2_fixed_T0_{t}h" for t in (1, 4, 12, 24, 72)] + [f"E3_adaptive_T0_{t}h" for t in (1, 4, 12, 24, 72)]
T0S = (1, 4, 12, 24, 72)
SUMS = ["jobs", "on_time", "late", "useful_h", "overhead_h", "lost_h", "recovery_h", "interrupted_h", "queue_h",
        "turnaround_h", "turn_ratio_sum", "checkpoints", "failures", "jobs_hit"]
C_H = 300.0 / 3600


def shard_tables(args):
    run_dir, k = args
    d = os.path.join(run_dir, f"shard_{k:02d}")
    inj = pd.read_csv(os.path.join(d, "injector_failures.csv"))
    st = pd.read_csv(os.path.join(d, "streams.csv"), dtype={"serial": str})
    tl = pd.read_csv(os.path.join(d, "tier_timeline.csv"), dtype={"serial": str})
    occ = tl[tl["day"].between(1, 30)].groupby(["stream", "tier"]).size().unstack(fill_value=0)
    for t in ("LOW", "MEDIUM", "HIGH"):
        if t not in occ:
            occ[t] = 0
    hosts = pd.DataFrame({"shard": k, "stream": st["stream"], "serial": st["serial"]})
    hosts["failing"] = hosts["stream"].isin(inj["stream"])
    hosts = hosts.join(occ[["LOW", "MEDIUM", "HIGH"]], on="stream").fillna(0)
    hosts["majority_tier"] = hosts[["LOW", "MEDIUM", "HIGH"]].idxmax(axis=1)
    per = {}
    ck_rows, fail_rows = [], []
    fail_set = set(inj["stream"])
    tier_day = tl.set_index(["stream", "day"])["tier"]
    for r in RUNS:
        rd = os.path.join(d, r)
        j = pd.read_csv(os.path.join(rd, "jobs.csv"), usecols=["stream", "length_sec", "queue_delay_sec", "turnaround_sec",
                                                               "success", "checkpoints", "checkpoint_overhead_sec",
                                                               "interrupted_write_sec", "failures", "lost_work_sec",
                                                               "recovery_sec"])
        g = j.groupby("stream")
        a = pd.DataFrame({"jobs": g.size(), "on_time": g["success"].sum(),
                          "useful_h": g["length_sec"].sum() / 3600, "overhead_h": g["checkpoint_overhead_sec"].sum() / 3600,
                          "lost_h": g["lost_work_sec"].sum() / 3600, "recovery_h": g["recovery_sec"].sum() / 3600,
                          "interrupted_h": g["interrupted_write_sec"].sum() / 3600,
                          "queue_h": g["queue_delay_sec"].sum() / 3600, "turnaround_h": g["turnaround_sec"].sum() / 3600,
                          "turn_ratio_sum": (j["turnaround_sec"] / j["length_sec"]).groupby(j["stream"]).sum(),
                          "checkpoints": g["checkpoints"].sum(), "failures": g["failures"].sum(),
                          "jobs_hit": (j["failures"] > 0).groupby(j["stream"]).sum()})
        a["late"] = a["jobs"] - a["on_time"]
        per[r] = a.reindex(hosts["stream"]).fillna(0)[SUMS].to_numpy(dtype=np.float64)
        # checkpoints by tier (tier in force when the checkpointed segment started)
        cnt = None
        for ch in pd.read_csv(os.path.join(rd, "checkpoint_events.csv.gz"), usecols=["stream", "tier"], chunksize=2_000_000):
            ch["failing"] = ch["stream"].isin(fail_set)
            vc = ch.groupby(["failing", "tier"]).size()
            cnt = vc if cnt is None else cnt.add(vc, fill_value=0)
        if cnt is not None:
            for (fl, t), v in cnt.items():
                ck_rows.append({"shard": k, "run": r, "failing": bool(fl), "tier": t, "checkpoints": int(v)})
        fe = pd.read_csv(os.path.join(rd, "failure_events.csv"), dtype={"serial": str})
        for f in fe.itertuples():
            day = int(f.time // 86400)
            fail_rows.append({"shard": k, "run": r, "serial": f.serial, "stream": f.stream, "time": f.time,
                              "phase": f.phase, "committed_h": f.committed_sec / 3600, "lost_h": f.lost_sec / 3600,
                              "tier_at_failure": tier_day.get((f.stream, day), "MEDIUM")})
    return hosts, per, ck_rows, fail_rows


def ratio_metrics(S):
    """S: (..., len(SUMS)) sums -> dict of metrics."""
    i = {k: n for n, k in enumerate(SUMS)}
    jobs = S[..., i["jobs"]]
    return {
        "on_time_pct": 100 * S[..., i["on_time"]] / jobs,
        "deadline_miss_pct": 100 * S[..., i["late"]] / jobs,
        "late_jobs": S[..., i["late"]],
        "lost_work_h": S[..., i["lost_h"]],
        "checkpoint_overhead_h": S[..., i["overhead_h"]],
        "overhead_pct_of_useful": 100 * S[..., i["overhead_h"]] / S[..., i["useful_h"]],
        "recovery_h": S[..., i["recovery_h"]],
        "wasted_pct_of_useful": 100 * (S[..., i["overhead_h"]] + S[..., i["lost_h"]] + S[..., i["recovery_h"]]
                                       + S[..., i["interrupted_h"]]) / S[..., i["useful_h"]],
        "queue_mean_h_per_job": S[..., i["queue_h"]] / jobs,
        "turnaround_mean_h_per_job": S[..., i["turnaround_h"]] / jobs,
        "turnaround_over_length_mean": S[..., i["turn_ratio_sum"]] / jobs,
        "checkpoints_per_job": S[..., i["checkpoints"]] / jobs,
        "failures": S[..., i["failures"]],
        "jobs_hit_by_failure": S[..., i["jobs_hit"]],
    }


def bootstrap_sums(X, B, seed):
    """X: (hosts, policies, sums). Poisson(1) host weights shared across policies -> (B, policies, sums)."""
    rng = np.random.default_rng(seed)
    H = X.shape[0]
    flat = X.reshape(H, -1)
    out = np.empty((B, flat.shape[1]))
    step = max(1, int(2e7 // max(H, 1)))
    for b0 in range(0, B, step):
        b1 = min(B, b0 + step)
        W = rng.poisson(1.0, size=(b1 - b0, H)).astype(np.float64)
        out[b0:b1] = W @ flat
    return out.reshape(B, X.shape[1], X.shape[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20190601)
    ap.add_argument("--only", default="", help="comma-separated shard subset (testing)")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.run_dir, "run_config.json")))
    shards = int(cfg["shards"])
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        parts = list(ex.map(shard_tables, [(a.run_dir, k) for k in ([int(x) for x in a.only.split(",")] if a.only else range(shards))]))
    hosts = pd.concat([p[0] for p in parts], ignore_index=True)
    X = np.stack([np.concatenate([p[1][r] for p in parts]) for r in RUNS], axis=1)     # (H, runs, sums)
    out = os.path.join(a.run_dir, "analysis")
    os.makedirs(out, exist_ok=True)
    ck = pd.DataFrame([row for p in parts for row in p[2]])
    fails = pd.DataFrame([row for p in parts for row in p[3]])
    fails.to_csv(os.path.join(out, "failures_detail.csv"), index=False)

    strata = {"all": np.ones(len(hosts), bool), "failing": hosts["failing"].to_numpy(),
              "non_failing": ~hosts["failing"].to_numpy()}
    # policy summaries with bootstrap CIs; paired comparisons
    comps = [(f"E3_adaptive_T0_{t}h", f"E2_fixed_T0_{t}h") for t in T0S] + \
            [(f"E2_fixed_T0_{t}h", "E1_none") for t in T0S] + [(f"E3_adaptive_T0_{t}h", "E1_none") for t in T0S]
    summ, pairs = [], []
    for sname, m in strata.items():
        Xs = X[m]
        point = ratio_metrics(Xs.sum(axis=0))                          # (runs,) per metric
        boot = ratio_metrics(bootstrap_sums(Xs, a.boot, a.seed + len(sname)))   # (B, runs)
        for ri, r in enumerate(RUNS):
            row = {"stratum": sname, "policy": r, "hosts": int(m.sum())}
            for k, v in point.items():
                row[k] = float(v[ri])
                lo, hi = np.nanpercentile(boot[k][:, ri], [2.5, 97.5])
                row[k + "_ci_lo"], row[k + "_ci_hi"] = float(lo), float(hi)
            summ.append(row)
        for x, y in comps:
            xi, yi = RUNS.index(x), RUNS.index(y)
            for k in point:
                diff = float(point[k][xi] - point[k][yi])
                bd = boot[k][:, xi] - boot[k][:, yi]
                lo, hi = np.nanpercentile(bd, [2.5, 97.5])
                pairs.append({"stratum": sname, "comparison": f"{x} - {y}", "metric": k,
                              "policy_a": float(point[k][xi]), "policy_b": float(point[k][yi]),
                              "difference": diff, "ci_lo": float(lo), "ci_hi": float(hi),
                              "ci_excludes_zero": bool(lo > 0 or hi < 0)})
    pd.DataFrame(summ).to_csv(os.path.join(out, "policy_summary.csv"), index=False)
    pd.DataFrame(pairs).to_csv(os.path.join(out, "paired_comparisons.csv"), index=False)

    # risk-tier breakdown: hosts grouped by majority June tier (days 1-30)
    tb = []
    for t in ("LOW", "MEDIUM", "HIGH"):
        for fl in (False, True):
            m = (hosts["majority_tier"] == t).to_numpy() & (hosts["failing"].to_numpy() == fl)
            if not m.any():
                continue
            pm = ratio_metrics(X[m].sum(axis=0))
            for ri, r in enumerate(RUNS):
                tb.append({"majority_tier": t, "failing": fl, "hosts": int(m.sum()), "policy": r,
                           **{k: float(v[ri]) for k, v in pm.items()}})
    pd.DataFrame(tb).to_csv(os.path.join(out, "tier_breakdown.csv"), index=False)

    # tier occupancy (host-days 1..30)
    occ = []
    for name, m in (("all", strata["all"]), ("failing", strata["failing"]), ("non_failing", strata["non_failing"])):
        tot = hosts.loc[m, ["LOW", "MEDIUM", "HIGH"]].sum()
        occ.append({"hosts": name, "n_hosts": int(m.sum()), "host_days": int(tot.sum()),
                    **{t: round(100 * tot[t] / tot.sum(), 3) for t in ("LOW", "MEDIUM", "HIGH")}})
    occ.append({"hosts": "validation_design_target", "n_hosts": None, "host_days": None, "LOW": 90.0, "MEDIUM": 9.0, "HIGH": 1.0})
    pd.DataFrame(occ).to_csv(os.path.join(out, "tier_occupancy.csv"), index=False)

    # checkpoints / overhead by tier
    ckt = ck.groupby(["run", "failing", "tier"])["checkpoints"].sum().reset_index()
    ckt["overhead_h"] = ckt["checkpoints"] * C_H
    ckt.to_csv(os.path.join(out, "checkpoints_by_tier.csv"), index=False)

    meta = {"run_dir": a.run_dir, "utilization": cfg["utilization"], "hosts": int(len(hosts)),
            "failing_hosts": int(hosts["failing"].sum()), "jobs": int(X[:, 0, 0].sum()), "bootstrap_B": a.boot,
            "bootstrap": "paired host-clustered Poisson(1) weights, percentile 95% CI", "seed": a.seed,
            "majority_tier_hosts": hosts["majority_tier"].value_counts().to_dict(),
            "failing_hosts_by_majority_tier": hosts.loc[hosts["failing"], "majority_tier"].value_counts().to_dict()}
    json.dump(meta, open(os.path.join(out, "analysis_meta.json"), "w"), indent=2)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
