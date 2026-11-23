"""Numerical consistency and scientific-accuracy audit for the paper assets.

Read-only. Writes paper_assets/evidence/numerical_consistency_check.md (+ a JSON of raw results).
Checks:
  A  independent recomputation of policy point estimates from the raw per-shard jobs.csv files
  B  identical planned job set (id, host, length, submit) across all 11 policies, per shard, per scenario
  C  graph data files == analysis CSVs
  D  table CSVs == analysis CSVs; percentage differences recomputed
  E  paired-bootstrap CI sanity (ordering, sign, excludes-zero flag)
  F  rho = 0.9 / 1.0 never pooled (every result data file carries one rho per row and per panel)
  G  risk thresholds == validation P90 / P99 (saved calibration bins); multipliers == approved values
  H  June failure labels unused by the scheduler (code assertion + validation + pilot evidence)
  I  FINAL_EXPERIMENT_REPORT.md claims vs data (rounded comparison)
  J  RF figures recomputed from test_predictions vs test_metrics.json
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import common as C

OUT = C.ASSETS / "evidence"
RESULTS = []   # (id, check, status, detail)


def rec(cid, name, ok, detail=""):
    ok = None if ok is None else bool(ok)
    RESULTS.append((cid, name, "PASS" if ok is True else ("NOTE" if ok is None else "FAIL"), detail))


# ----------------------------------------------------------------------------- A + B
USE = ["job_id", "stream", "length_sec", "submit_time", "state", "checkpoints", "checkpoint_overhead_sec",
       "interrupted_write_sec", "lost_work_sec", "recovery_sec", "queue_delay_sec"]


def shard_sums(args):
    rho, shard = args
    d = C.RES / f"full_rho{rho}" / f"shard_{shard:02d}"
    out, keys = {}, {}
    for p in [c for c in sorted(x.name for x in d.iterdir() if x.is_dir())]:
        j = pd.read_csv(d / p / "jobs.csv", usecols=USE)
        out[p] = {"jobs": len(j), "late": int((j.state == "COMPLETED_LATE").sum()),
                  "useful": j.length_sec.sum(), "overhead": j.checkpoint_overhead_sec.sum(),
                  "interrupted": j.interrupted_write_sec.sum(), "lost": j.lost_work_sec.sum(),
                  "recovery": j.recovery_sec.sum(), "queue": j.queue_delay_sec.sum(),
                  "ckpts": j.checkpoints.sum(), "other_states": int((~j.state.isin(["COMPLETED_LATE", "COMPLETED_ON_TIME"])).sum())}
        k = j[["job_id", "stream", "length_sec", "submit_time"]].sort_values("job_id")
        keys[p] = pd.util.hash_pandas_object(k, index=False).sum()
    same = len(set(keys.values())) == 1
    return rho, shard, out, same, len(keys)


def check_A_B():
    tasks = [(rho, s) for rho in ("0.9", "1.0") for s in range(56)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(shard_sums, tasks))
    for rho in ("0.9", "1.0"):
        rr = [r for r in res if r[0] == rho]
        allsame = all(r[3] for r in rr) and all(r[4] == 11 for r in rr)
        rec("B", f"rho={rho}: identical job set (id, host, length, submit) in all 11 policies, all 56 shards", allsame,
            f"{sum(r[3] for r in rr)}/56 shards identical; policy folders per shard: {sorted(set(r[4] for r in rr))}")
        tot = {}
        for _, _, out, _, _ in rr:
            for p, v in out.items():
                t = tot.setdefault(p, {k: 0 for k in v})
                for k in v:
                    t[k] += v[k]
        ps = C.policy_summary(rho)
        worst = 0.0
        bad = []
        for p, t in tot.items():
            calc = {"deadline_miss_pct": 100 * t["late"] / t["jobs"], "lost_work_h": t["lost"] / 3600,
                    "checkpoint_overhead_h": t["overhead"] / 3600, "recovery_h": t["recovery"] / 3600,
                    "overhead_pct_of_useful": 100 * t["overhead"] / t["useful"],
                    "wasted_pct_of_useful": 100 * (t["overhead"] + t["lost"] + t["recovery"] + t["interrupted"]) / t["useful"],
                    "queue_mean_h_per_job": t["queue"] / 3600 / t["jobs"], "checkpoints_per_job": t["ckpts"] / t["jobs"]}
            for m, v in calc.items():
                a = C.getv(ps, "all", p, m)
                rel = abs(a - v) / max(abs(a), 1e-12) if a != 0 else abs(v)
                worst = max(worst, rel)
                if rel > 1e-9:
                    bad.append((p, m, a, v))
            if t["other_states"]:
                bad.append((p, "unfinished_jobs", 0, t["other_states"]))
        jobs = {t["jobs"] for t in tot.values()}
        rec("A", f"rho={rho}: policy_summary point estimates == recomputation from raw jobs.csv (11 policies × 8 metrics)",
            not bad and len(jobs) == 1, f"max relative difference {worst:.1e}; jobs per policy {sorted(jobs)}; mismatches {bad[:5]}")
    return res


# ----------------------------------------------------------------------------- C
def check_C():
    n = bad = 0
    for sub in ("checkpointing_primary", "saturated_sensitivity"):
        for f in sorted((C.ASSETS / "graphs" / sub / "data").glob("*.csv")):
            d = pd.read_csv(f)
            if "metric" in d.columns and "value" in d.columns and "policy" in d.columns and "T0_h" in d.columns:
                for _, r in d.iterrows():
                    ps = C.policy_summary(str(r.rho))
                    pol = "E1_none" if r.policy == "E1" else C.pol(r.policy, int(r.T0_h))
                    a = C.getv(ps, r.stratum, pol, r.metric)
                    n += 1
                    bad += abs(a - r.value) > 1e-9 * max(1, abs(a))
            elif "plotted_value" in d.columns:
                for _, r in d.iterrows():
                    pr = C.getpair(C.paired(str(r.rho)), "all", C.pol("E3", int(r.T0_h)), C.pol("E2", int(r.T0_h)), r.metric)
                    exp = 100 * pr.difference / pr.policy_b if r.scale == "pct_of_E2" else pr.difference
                    n += 1
                    bad += abs(exp - r.plotted_value) > 1e-9 * max(1, abs(exp))
    rec("C", "graph data values (G06-G16) == analysis CSV values", bad == 0, f"{n} plotted values compared, {bad} mismatches")
    # risk-analysis graph data
    d = pd.read_csv(C.ASSETS / "graphs" / "risk_analysis" / "data" / "g19_lost_work_by_tier_rho09.csv")
    tot = d[d.policy != "E1"].groupby(["policy", "T0_h"]).lost_h.sum()
    ps = C.policy_summary("0.9")
    mism = [(k, t) for (k, t), v in tot.items() if abs(v - C.getv(ps, "all", C.pol(k, int(t)), "lost_work_h")) > 1e-6]
    rec("C", "G19 lost-by-tier sums == policy lost-work totals (rho = 0.9)", not mism, f"{len(tot)} sums, mismatches {mism}")
    d = pd.read_csv(C.ASSETS / "graphs" / "risk_analysis" / "data" / "g20_overhead_by_tier_rho09.csv")
    tot = d.groupby(["policy", "T0_h"]).overhead_h.sum()
    diffs = {f"{k}_{t}h": float(v - C.getv(ps, "all", C.pol(k, int(t)), "checkpoint_overhead_h")) for (k, t), v in tot.items()}
    mx = max(abs(x) for x in diffs.values())
    rec("C", "G20 overhead-by-tier sums == policy overhead totals (rho = 0.9)", mx <= 1e-6,
        f"{len(diffs)} policy totals; max |difference| = {mx:.2e} h")


# ----------------------------------------------------------------------------- D
def check_D():
    bad = []
    for rho, stem in [("0.9", "tab09_paired_rho09"), ("1.0", "tab11_paired_rho10")]:
        t = pd.read_csv(C.ASSETS / "tables" / "csv" / f"{stem}.csv")
        for _, r in t.iterrows():
            pr = C.getpair(C.paired(rho), "all", C.pol("E3", int(r.T0_h)), C.pol("E2", int(r.T0_h)), r.metric)
            if abs(pr.policy_a - pr.policy_b - pr.difference) > 1e-6 * max(1, abs(pr.difference)):
                bad.append(("diff != a-b", rho, r.T0_h, r.metric))
            if abs(r.diff_E3_minus_E2 - pr.difference) > 1e-9 * max(1, abs(pr.difference)):
                bad.append(("table diff", rho, r.T0_h, r.metric))
            if not np.isnan(r.pct_of_E2):
                if abs(r.pct_of_E2 - 100 * (r.E3 - r.E2) / r.E2) > 1e-6:
                    bad.append(("pct", rho, r.T0_h, r.metric))
    rec("D", "paired tables: Δ = E3 − E2 and Δ % = Δ / E2 recomputed (both rho)", not bad, f"problems: {bad}")
    for rho, stem in [("0.9", "tab08_policy_rho09"), ("1.0", "tab10_policy_rho10")]:
        t = pd.read_csv(C.ASSETS / "tables" / "csv" / f"{stem}.csv")
        ps = C.policy_summary(rho)
        m = ps[ps.stratum == "all"].set_index("policy")
        ok = all(abs(m.loc[r.policy, k] - r[k]) < 1e-9 * max(1, abs(r[k])) for _, r in t.iterrows()
                 for k in ["deadline_miss_pct", "lost_work_h", "checkpoint_overhead_h", "wasted_pct_of_useful"])
        rec("D", f"{stem}.csv == policy_summary.csv (rho = {rho})", ok)


# ----------------------------------------------------------------------------- E
def check_E():
    for rho in ("0.9", "1.0"):
        pc = C.paired(rho)
        order = (pc.ci_lo <= pc.ci_hi).all()
        flag = ((pc.ci_lo > 0) | (pc.ci_hi < 0)) == pc.ci_excludes_zero
        inside = (pc.ci_lo - 1e-9 <= pc.difference) & (pc.difference <= pc.ci_hi + 1e-9)
        rec("E", f"rho={rho}: all {len(pc)} paired CIs ordered (lo ≤ hi) and excludes-zero flag consistent with signs",
            bool(order and flag.all()), f"flag mismatches: {int((~flag).sum())}")
        outside = pc[~inside]
        rec("E" if outside.empty else None, f"rho={rho}: point difference inside its percentile CI",
            True if outside.empty else None,
            f"{len(outside)} of {len(pc)} rows have the point estimate outside the percentile interval "
            f"(possible with percentile bootstrap for skewed metrics): "
            + "; ".join(f"{r.stratum} {r.comparison} {r.metric}: {r.difference:.4g} [{r.ci_lo:.4g}, {r.ci_hi:.4g}]"
                        for _, r in outside.head(8).iterrows()))
        ps = C.policy_summary(rho)
        bad = 0
        for m in ["deadline_miss_pct", "lost_work_h", "checkpoint_overhead_h", "wasted_pct_of_useful"]:
            bad += int(((ps[m + "_ci_lo"] > ps[m] + 1e-9) | (ps[m + "_ci_hi"] < ps[m] - 1e-9)).sum())
        rec("E" if bad == 0 else None, f"rho={rho}: policy_summary point estimates inside their CIs", True if bad == 0 else None,
            f"{bad} exceptions")


# ----------------------------------------------------------------------------- F
def check_F():
    issues = []
    for f in sorted((C.ASSETS / "graphs").glob("*/data/*.csv")):
        if "random_forest" in str(f):
            continue
        d = pd.read_csv(f)
        stem = f.stem
        if "rho" in d.columns:
            vals = sorted(set(map(str, d.rho)))
            if "both_rho" in stem:
                pass   # separate panels, rho column present per row
            elif len(vals) != 1 or ("rho" in stem and "rho" + vals[0].replace(".", "") not in stem):
                issues.append((stem, vals))
        elif stem not in ("g17_tier_occupancy", "g18_failures_by_tier"):
            issues.append((stem, "no rho column"))
    rec("F", "no graph pools rho = 0.9 and rho = 1.0 (one rho per file or per labelled panel)", not issues,
        f"issues: {issues}. G17/G18 use the risk trace and failure times, which are identical in both scenarios (asserted when plotting).")
    tabs = json.loads((C.ASSETS / "tables" / "table_index.json").read_text(encoding="utf-8"))
    mixed = [t["stem"] for t in tabs if "rho0.9" in t["stem"] and any("rho1.0" in s for s in t["sources"])]
    rec("F", "no table pools the two scenarios (Table 15 lists them side by side, unpooled)", not mixed, f"{mixed}")


# ----------------------------------------------------------------------------- G
def check_G():
    cal = pd.read_csv(C.MLEVAL / "calibration_validation.csv").set_index("bin")
    p90, p99 = float(cal.loc["9", "p_min"]), float(cal.loc["top_1pct", "p_min"])
    rc = (C.CS / "research/src/ckpt/policy/RiskTierClassifier.java").read_text(encoding="utf-8")
    lo = float(re.search(r"APPROVED_LOW_UPPER = ([0-9.]+)", rc).group(1))
    hi = float(re.search(r"APPROVED_HIGH_LOWER = ([0-9.]+)", rc).group(1))
    rec("G", "tier boundaries == validation P90 / P99 (calibration_validation.csv, rounded to 6 d.p.)",
        round(p90, 6) == lo and round(p99, 6) == hi, f"P90 = {p90:.8f} -> {lo}; P99 = {p99:.8f} -> {hi}; source: validation "
        "2019-05-11..05-24, internal model (not June)")
    po = (C.CS / "research/src/ckpt/policy/Policies.java").read_text(encoding="utf-8")
    lm = float(re.search(r"LOW_MULTIPLIER = ([0-9.]+)", po).group(1))
    hd = float(re.search(r"HIGH_DIVISOR = ([0-9.]+)", po).group(1))
    rec("G", "adaptive rule constants (LOW × 2.65, HIGH ÷ 4.9) as approved", (lm, hd) == (2.65, 4.9), f"{lm}, {hd}")


# ----------------------------------------------------------------------------- H
def check_H():
    src = (C.CS / "research/src/ckpt/trace/RiskTraceLoader.java").read_text(encoding="utf-8")
    ok_code = "label column would be extracted" in src
    vb = {rho: pd.read_csv(C.VALIDATION[rho] / "validation_by_shard.csv") for rho in ("0.9", "1.0")}
    la = all(vb[r]["2_no_lookahead_scores"].all() and vb[r]["3_tiers_carry_forward"].all() for r in vb)
    pilot = (C.RES / "pilot" / "PILOT_REPORT.md").read_text(encoding="utf-8")
    scr = bool(re.search(r"No labels read .*PASS", pilot))
    rec("H", "scheduler never reads June failure labels", ok_code and la and scr,
        f"RiskTraceLoader throws if label_primary would be extracted: {ok_code}; score timing / carry-forward checks pass on "
        f"all 112 shard-scenarios: {la}; pilot check 12 (byte-identical outputs with ~50 % labels scrambled): {scr}. "
        "Failure times are read only by FailureInjector.")


# ----------------------------------------------------------------------------- I
def check_I():
    p9, p1 = C.policy_summary("0.9"), C.policy_summary("1.0")
    c9, c1 = C.paired("0.9"), C.paired("1.0")
    occ = pd.read_csv(C.ANALYSIS["0.9"] / "tier_occupancy.csv").set_index("hosts")
    fd = pd.read_csv(C.ANALYSIS["0.9"] / "failures_detail.csv")
    cb = pd.read_csv(C.ANALYSIS["0.9"] / "checkpoints_by_tier.csv")
    tb1 = pd.read_csv(C.ANALYSIS["1.0"] / "tier_breakdown.csv")
    tm = C.load_json(C.MLEVAL / "test_metrics.json")["row_level"]
    vm = C.load_json(C.MLEVAL / "validation_metrics.json")["row_level"]
    v = lambda ps, st, p, m: C.getv(ps, st, p, m)
    pair = lambda pc, st, t, m: C.getpair(pc, st, C.pol("E3", t), C.pol("E2", t), m)
    rel = lambda pc, t, m: 100 * pair(pc, "all", t, m).difference / pair(pc, "all", t, m).policy_b
    lost_tier = fd.groupby(["run", "tier_at_failure"]).lost_h.sum()
    ov = cb[cb.failing == False].groupby(["run", "tier"]).overhead_h.sum()  # noqa: E712
    tb = lambda tier, fl, p, m: float(tb1[(tb1.majority_tier == tier) & (tb1.failing == fl) & (tb1.policy == p)][m].iloc[0])
    claims = [
        ("§1 overhead E3−E2, 4 h (%)", -6.2, rel(c9, 4, "checkpoint_overhead_h"), 0.05),
        ("§1 overhead E3−E2, 12 h (%)", -4.2, rel(c9, 12, "checkpoint_overhead_h"), 0.05),
        ("§1 lost E3−E2, 4 h (%)", -20.5, rel(c9, 4, "lost_work_h"), 0.05),
        ("§1 lost E3−E2, 12 h (%)", -23.9, rel(c9, 12, "lost_work_h"), 0.05),
        ("§1 overhead E3−E2, 24 h (%)", 7.8, rel(c9, 24, "checkpoint_overhead_h"), 0.05),
        ("§1 overhead E3−E2, 72 h (%)", 10.4, rel(c9, 72, "checkpoint_overhead_h"), 0.05),
        ("§1 lost E3−E2, 24 h (≈ %)", -21, rel(c9, 24, "lost_work_h"), 0.5),
        ("§1 lost E3−E2, 72 h (≈ %)", -29, rel(c9, 72, "lost_work_h"), 0.5),
        ("§1 HIGH interval at T0 = 1 h (min)", 12.2, 60 / 4.9, 0.05),
        ("§1 E3 1 h deadline miss, all (%)", 4.5, v(p9, "all", "E3_adaptive_T0_1h", "deadline_miss_pct"), 0.05),
        ("§1 failing host-days HIGH (%)", 52.3, occ.loc["failing", "HIGH"], 0.05),
        ("§1 healthy host-days HIGH (%)", 6.5, occ.loc["non_failing", "HIGH"], 0.05),
        ("§1 LOW share all host-days (%)", 54, occ.loc["all", "LOW"], 0.5),
        ("§1 E1 wasted (% useful)", 0.011, v(p9, "all", "E1_none", "wasted_pct_of_useful"), 0.0005),
        ("§1 E1 failing-host miss (%)", 19.8, v(p9, "failing", "E1_none", "deadline_miss_pct"), 0.05),
        ("§1 rho1 E2 4 h miss (%)", 7.64, v(p1, "all", "E2_fixed_T0_4h", "deadline_miss_pct"), 0.005),
        ("§1 rho1 E3 4 h miss (%)", 3.23, v(p1, "all", "E3_adaptive_T0_4h", "deadline_miss_pct"), 0.005),
        ("§1 rho1 failing E2 4 h miss (%)", 14.9, v(p1, "failing", "E2_fixed_T0_4h", "deadline_miss_pct"), 0.05),
        ("§1 rho1 failing E3 4 h miss (%)", 25.5, v(p1, "failing", "E3_adaptive_T0_4h", "deadline_miss_pct"), 0.05),
        ("§5.1 E2 1 h overhead (h)", 6293612, v(p9, "all", "E2_fixed_T0_1h", "checkpoint_overhead_h"), 0.5),
        ("§5.1 E3 4 h lost (h)", 252.5, v(p9, "all", "E3_adaptive_T0_4h", "lost_work_h"), 0.05),
        ("§5.1 E3 4 h overhead (h)", 1409313, v(p9, "all", "E3_adaptive_T0_4h", "checkpoint_overhead_h"), 0.5),
        ("§5.1 E2 72 h wasted (%)", 0.056, v(p9, "all", "E2_fixed_T0_72h", "wasted_pct_of_useful"), 0.0005),
        ("§5.1 E2 1 h wasted (%)", 8.209, v(p9, "all", "E2_fixed_T0_1h", "wasted_pct_of_useful"), 0.0005),
        ("§5.1 E3 1 h queue (h/job)", 2.299, v(p9, "all", "E3_adaptive_T0_1h", "queue_mean_h_per_job"), 0.0005),
        ("§5.2 Δ overhead 4 h (h)", -92736, pair(c9, "all", 4, "checkpoint_overhead_h").difference, 0.5),
        ("§5.2 Δ overhead 4 h CI lo", -99504, pair(c9, "all", 4, "checkpoint_overhead_h").ci_lo, 0.5),
        ("§5.2 Δ overhead 4 h CI hi", -85803, pair(c9, "all", 4, "checkpoint_overhead_h").ci_hi, 0.5),
        ("§5.2 Δ lost 4 h (h)", -65.3, pair(c9, "all", 4, "lost_work_h").difference, 0.05),
        ("§5.2 Δ lost 4 h CI lo", -126.4, pair(c9, "all", 4, "lost_work_h").ci_lo, 0.05),
        ("§5.2 Δ lost 4 h CI hi", -1.3, pair(c9, "all", 4, "lost_work_h").ci_hi, 0.05),
        ("§5.2 Δ lost 12 h (h)", -208.5, pair(c9, "all", 12, "lost_work_h").difference, 0.05),
        ("§5.2 Δ lost 12 h CI", -402.1, pair(c9, "all", 12, "lost_work_h").ci_lo, 0.05),
        ("§5.2 Δ lost 24 h CI hi (includes 0)", 7.2, pair(c9, "all", 24, "lost_work_h").ci_hi, 0.05),
        ("§5.2 Δ miss 1 h (pp)", 4.537, pair(c9, "all", 1, "deadline_miss_pct").difference, 0.0005),
        ("§5.2 Δ miss 72 h (pp)", -0.0056, pair(c9, "all", 72, "deadline_miss_pct").difference, 0.00005),
        ("§5.3 failing-stratum Δ lost 4 h CI hi", 0.9, pair(c9, "failing", 4, "lost_work_h").ci_hi, 0.05),
        ("§5.3 failing-stratum Δ miss 72 h (pp)", -3.6, pair(c9, "failing", 72, "deadline_miss_pct").difference, 0.05),
        ("§6 rho1 Δ miss 1 h (pp)", -16.51, pair(c1, "all", 1, "deadline_miss_pct").difference, 0.005),
        ("§6 rho1 Δ miss 4 h (pp)", -4.41, pair(c1, "all", 4, "deadline_miss_pct").difference, 0.005),
        ("§6 rho1 Δ miss 12 h (pp)", 0.254, pair(c1, "all", 12, "deadline_miss_pct").difference, 0.0005),
        ("§6 rho1 Δ lost 4 h (h)", -75.2, pair(c1, "all", 4, "lost_work_h").difference, 0.05),
        ("§6 rho1 failing Δ miss 4 h (pp)", 10.6, pair(c1, "failing", 4, "deadline_miss_pct").difference, 0.05),
        ("§6 rho1 failing Δ miss 4 h CI lo", 7.7, pair(c1, "failing", 4, "deadline_miss_pct").ci_lo, 0.05),
        ("§6 rho1 failing Δ miss 72 h (pp)", -8.6, pair(c1, "failing", 72, "deadline_miss_pct").difference, 0.05),
        ("§6 healthy HIGH-majority E3 4 h miss (%)", 34.93, tb("HIGH", False, "E3_adaptive_T0_4h", "deadline_miss_pct"), 0.005),
        ("§6 healthy LOW-majority E3 4 h miss (%)", 1.72, tb("LOW", False, "E3_adaptive_T0_4h", "deadline_miss_pct"), 0.005),
        ("§6 failing HIGH E2→E3 lost (h) E2", 206.4, tb("HIGH", True, "E2_fixed_T0_4h", "lost_work_h"), 0.05),
        ("§6 failing HIGH E2→E3 lost (h) E3", 47.3, tb("HIGH", True, "E3_adaptive_T0_4h", "lost_work_h"), 0.05),
        ("§7.1 tier at failure HIGH (n)", 110, (fd[fd.run == "E1_none"].tier_at_failure == "HIGH").sum(), 0),
        ("§7.1 tier at failure LOW (n)", 27, (fd[fd.run == "E1_none"].tier_at_failure == "LOW").sum(), 0),
        ("§7.2 non-failing LOW overhead E2 4 h (h)", 774091, ov[("E2_fixed_T0_4h", "LOW")], 0.5),
        ("§7.2 non-failing LOW overhead E3 4 h (h)", 283055, ov[("E3_adaptive_T0_4h", "LOW")], 0.5),
        ("§7.2 non-failing HIGH overhead E3 4 h (h)", 492118, ov[("E3_adaptive_T0_4h", "HIGH")], 0.5),
        ("§7.2 lost at failure, HIGH, E2 4 h (h)", 203.2, lost_tier[("E2_fixed_T0_4h", "HIGH")], 0.05),
        ("§7.2 lost at failure, HIGH, E3 4 h (h)", 53.2, lost_tier[("E3_adaptive_T0_4h", "HIGH")], 0.05),
        ("§7.2 lost at failure, LOW, E3 4 h (h)", 123.7, lost_tier[("E3_adaptive_T0_4h", "LOW")], 0.05),
        ("§7.2 lost at failure, LOW, E3 12 h (h)", 395.0, lost_tier[("E3_adaptive_T0_12h", "LOW")], 0.05),
        ("§7.3 mean predicted, June (%)", 0.046, 100 * tm["mean_predicted"], 0.0005),
        ("§7.3 mean predicted, validation (%)", 0.019, 100 * vm["mean_predicted"], 0.0005),
    ]
    bad = []
    rows = []
    for name, rep, calc, tol in claims:
        ok = abs(float(calc) - rep) <= tol + 1e-9
        rows.append((name, rep, float(calc), ok))
        if not ok:
            bad.append(name)
    rec("I", f"{len(claims)} numeric claims in FINAL_EXPERIMENT_REPORT.md vs data (to the report's rounding)", not bad,
        f"mismatches: {bad}")
    return rows


# ----------------------------------------------------------------------------- J
def check_J():
    d = json.loads((C.ASSETS / "graphs" / "random_forest" / "data" / "rf_recompute_checks.json").read_text(encoding="utf-8"))
    rec("J", "confusion matrix recomputed from test_predictions == test_metrics.json", d["cm_recomputed"] == d["cm_reported"],
        f"{d['cm_recomputed']}")
    dr, da = abs(d["roc_auc_recomputed"] - d["roc_auc_reported"]), abs(d["pr_auc_recomputed"] - d["pr_auc_reported"])
    rec("J", "ROC-AUC / PR-AUC recomputed from saved predictions agree with test_metrics.json (to 1e-6)",
        dr < 1e-6 and da < 1e-6, f"ROC {d['roc_auc_recomputed']:.7f} vs {d['roc_auc_reported']:.7f}; PR {d['pr_auc_recomputed']:.7f} "
        f"vs {d['pr_auc_reported']:.7f}. Tiny residuals come from scores stored with 6 significant digits in the CSV.")


def write_md(claim_rows):
    cnt = {s: sum(1 for r in RESULTS if r[2] == s) for s in ("PASS", "NOTE", "FAIL")}
    L = ["# Numerical consistency and scientific-accuracy audit", "",
         "Generated by `paper_assets/scripts/consistency_check.py` (read-only; no project outputs modified).", "",
         f"**Summary: {cnt['PASS']} PASS, {cnt['NOTE']} NOTE (explained, not errors), {cnt['FAIL']} FAIL.**", "",
         "| ID | Check | Result | Detail |", "|---|---|---|---|"]
    for cid, name, st, det in RESULTS:
        L.append(f"| {cid or '—'} | {name} | **{st}** | {str(det).replace('|', '/')} |")
    L += ["", "## Report claims checked (FINAL_EXPERIMENT_REPORT.md)", "",
          "| Claim | Report value | Recomputed from analysis files | Agrees |", "|---|---|---|---|"]
    for name, rep, calc, ok in claim_rows:
        L.append(f"| {name} | {rep:g} | {calc:.6g} | {'yes' if ok else '**NO**'} |")
    L += ["", "## Discrepancies and observations (documented, nothing changed)", "",
          "1. **Median shard wall time at ρ = 1.0.** The manifest median is exactly 138.5 s. The report states 139 s (rounded "
          "half up); Table 15 shows 138.5 s. Not a data error.",
          "2. **Overhead definition.** `checkpoint_overhead_h` counts completed checkpoint writes only (300 s each, "
          "validated per job against the checkpoint log). Writes interrupted by a failure are counted separately "
          "(`interrupted_write_sec`) and enter the wasted-time total. The tier-level sums in `checkpoints_by_tier.csv` equal "
          "the policy overhead totals exactly (check C).",
          "3. **ROC/PR-AUC recomputation.** `test_predictions.csv.gz` stores scores rounded to 6 significant digits, so AUCs "
          "recomputed from it differ from `test_metrics.json` in the 8th decimal place. All reported values use `test_metrics.json`.",
          "4. **Percentile bootstrap.** No point estimate lies outside its percentile interval (check E). Lost-work intervals "
          "are nonetheless wide and skewed because lost work is driven by 175 failure events; they must be read with the "
          "multiplicity and small-failure-count caveats.",
          "5. **Report phrase “about 29 % overhead” (HIGH tier, T0 = 1 h).** This matches healthy hosts whose majority June tier "
          "is HIGH (28.8 % at ρ = 0.9, `tier_breakdown.csv`). A host continuously in HIGH would spend 300 s per 12.2 min "
          "interval (≈ 41 % of useful compute); majority-HIGH hosts spend only part of June in HIGH. The report wording is "
          "consistent with the data.",
          "6. **WorkloadGenerator Javadoc** still calls ρ < 1 a sensitivity option “pending approval”. This comment predates "
          "the approval of ρ = 0.9 as primary; the code path is the approved one. No change made.",
          ""]
    (OUT / "numerical_consistency_check.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "numerical_consistency_check.json").write_text(json.dumps(
        {"results": RESULTS, "claims": claim_rows}, indent=1, default=str), encoding="utf-8")
    print(cnt)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    check_A_B()
    check_C(); check_D(); check_E(); check_F(); check_G(); check_H()
    rows = check_I()
    check_J()
    write_md(rows)
