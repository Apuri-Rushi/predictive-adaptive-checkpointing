"""Checkpointing, saturated-sensitivity and risk-analysis graphs (G06-G20).

Sources (read-only): cloudsim/results/full_rho{0.9,1.0}/analysis/*.csv
  policy_summary.csv       - point estimates + host-clustered bootstrap 95 % CIs per policy and stratum
  paired_comparisons.csv   - paired differences (policy_a - policy_b) with bootstrap CIs
  tier_occupancy.csv, failures_detail.csv, checkpoints_by_tier.csv
rho = 0.9 and rho = 1.0 are never pooled: every panel states its scenario.
"""
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import common as C
from common import plt

G = C.ASSETS / "graphs"
P_OUT, S_OUT, R_OUT = G / "checkpointing_primary", G / "saturated_sensitivity", G / "risk_analysis"
T0S = C.T0S
XL = [f"{t} h" for t in T0S]


def ddir(out):
    d = out / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def series(ps, kind, metric, stratum="all"):
    v = np.array([C.getv(ps, stratum, C.pol(kind, t), metric) for t in T0S])
    lo = np.array([C.getv(ps, stratum, C.pol(kind, t), metric, "_ci_lo") for t in T0S])
    hi = np.array([C.getv(ps, stratum, C.pol(kind, t), metric, "_ci_hi") for t in T0S])
    return v, lo, hi


def grouped(ax, ps, metric, stratum="all", log=False, e1_line=True, label_fmt=None, e1_label_fmt="{:.3g}"):
    """Grouped E2/E3 bars per T0 with 95 % bootstrap CI whiskers; optional E1 reference line."""
    x = np.arange(len(T0S))
    w = 0.38
    rows = []
    for k, off in [("E2", -w / 2), ("E3", w / 2)]:
        v, lo, hi = series(ps, k, metric, stratum)
        ax.bar(x + off, v, w, color=C.POLICY_COLOR[k], edgecolor="white", linewidth=0.8, label=C.POLICY_LABEL[k],
               zorder=2)
        ax.errorbar(x + off, v, yerr=[np.clip(v - lo, 0, None), np.clip(hi - v, 0, None)], fmt="none",
                    ecolor=C.INK, elinewidth=0.6, capsize=1.6, zorder=3)
        if label_fmt:
            for xi, vi, hii in zip(x + off, v, hi):
                yy = max(vi, hii)
                ax.text(xi, yy * (1.15 if log else 1) + (0 if log else ax_pad(ax)), label_fmt(vi),
                        ha="center", va="bottom", fontsize=5.6, color=C.INK2, rotation=0)
        for t, vi, l, h in zip(T0S, v, lo, hi):
            rows.append({"policy": k, "T0_h": t, "stratum": stratum, "metric": metric, "value": vi, "ci_lo": l, "ci_hi": h})
    if e1_line:
        e1 = C.getv(ps, stratum, "E1_none", metric)
        ax.axhline(e1, color=C.C_E1, lw=1.2, ls="--", zorder=1, label=f"{C.POLICY_LABEL['E1']} ({e1_label_fmt.format(e1)})")
        rows.append({"policy": "E1", "T0_h": None, "stratum": stratum, "metric": metric, "value": e1,
                     "ci_lo": C.getv(ps, stratum, "E1_none", metric, "_ci_lo"),
                     "ci_hi": C.getv(ps, stratum, "E1_none", metric, "_ci_hi")})
    ax.set_xticks(x, XL)
    ax.set_xlabel("Baseline interval $T_0$")
    if log:
        ax.set_yscale("log")
    return rows


def ax_pad(ax):
    return 0.0


def legend_below(fig, ax, ncol=3, y=-0.02):
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=ncol, bbox_to_anchor=(0.5, y), fontsize=6.5, handlelength=1.6,
               columnspacing=1.0)


def simple_metric_fig(rho, metric, ylabel, out, stem, log=False, stratum="all", label_fmt=None, e1=True,
                      e1fmt="{:.3g}", title=None, ylim=None):
    ps = C.policy_summary(rho)
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.35))
    rows = grouped(ax, ps, metric, stratum, log=log, e1_line=e1, label_fmt=label_fmt, e1_label_fmt=e1fmt)
    ax.set_ylabel(ylabel + ("\n(log scale)" if log else ""))
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_title(title or f"$\\rho$ = {rho}, {'all hosts' if stratum == 'all' else stratum.replace('_', '-') + ' hosts'}",
                 fontsize=8)
    legend_below(fig, ax, ncol=2 if e1 else 2)
    fig.tight_layout(rect=(0, 0.13 if e1 else 0.08, 1, 1))
    C.save(fig, out, stem)
    pd.DataFrame(rows).assign(rho=rho).to_csv(ddir(out) / f"{stem}.csv", index=False)


def main():
    C.apply_style()
    fmt2 = lambda v: f"{v:.2f}"
    fmt_h = lambda v: f"{v:,.0f}"

    # ======================= PRIMARY rho = 0.9 =======================
    simple_metric_fig("0.9", "overhead_pct_of_useful", "Checkpoint overhead (% of useful)", P_OUT,
                      "g06_overhead_vs_T0_rho09", log=True, e1=False, label_fmt=lambda v: f"{v:.3f}" if v < 0.1 else f"{v:.3g}")
    simple_metric_fig("0.9", "lost_work_h", "Lost computation (h)", P_OUT, "g07_lost_work_vs_T0_rho09", log=True,
                      label_fmt=fmt_h, e1fmt="{:,.0f} h")

    # G08 deadline miss: (a) all hosts, (b) failing hosts
    ps = C.policy_summary("0.9")
    fig, axs = plt.subplots(1, 2, figsize=(C.DBL_W * 0.72, 2.3))
    rows = []
    for ax, st, ttl in [(axs[0], "all", "(a) $\\rho$ = 0.9, all hosts (110,848)"), (axs[1], "failing", "(b) $\\rho$ = 0.9, failing hosts (175)")]:
        rows += grouped(ax, ps, "deadline_miss_pct", st, label_fmt=(lambda v: f"{v:.2f}" if v >= 0.05 else "") if st == "all" else (lambda v: f"{v:.1f}"),
                        e1_label_fmt="{:.3g} %")
        ax.set_title(ttl, fontsize=8)
        ax.set_ylabel("Deadline miss rate (% of jobs)")
        ax.legend(loc="upper right", fontsize=6.2, handlelength=1.4)
    fig.tight_layout()
    C.save(fig, P_OUT, "g08_deadline_miss_vs_T0_rho09")
    pd.DataFrame(rows).assign(rho="0.9").to_csv(ddir(P_OUT) / "g08_deadline_miss_vs_T0_rho09.csv", index=False)

    # G09 wasted computation, all 11 policies
    rows = []
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.4))
    names, vals, los, his, cols = [], [], [], [], []
    for p in ["E1_none"] + [C.pol(k, t) for t in T0S for k in ("E2", "E3")]:
        v = C.getv(ps, "all", p, "wasted_pct_of_useful")
        lo, hi = C.getv(ps, "all", p, "wasted_pct_of_useful", "_ci_lo"), C.getv(ps, "all", p, "wasted_pct_of_useful", "_ci_hi")
        k = p[:2]
        names.append("E1" if k == "E1" else f"{k}\n{p.split('_')[-1]}")
        vals.append(v); los.append(lo); his.append(hi); cols.append(C.POLICY_COLOR[k])
        rows.append({"policy": p, "metric": "wasted_pct_of_useful", "value": v, "ci_lo": lo, "ci_hi": hi})
    xs = np.array([0] + [1.3 + i + 0.35 * (i // 2) for i in range(10)])
    ax.bar(xs, vals, 0.85, color=cols, edgecolor="white", linewidth=0.8, zorder=2)
    ax.errorbar(xs, vals, yerr=[np.array(vals) - los, np.array(his) - vals], fmt="none", ecolor=C.INK, elinewidth=0.6,
                capsize=1.4, zorder=3)
    for xi, v in zip(xs, vals):
        ax.text(xi, v * 1.18, f"{v:.3g}", ha="center", va="bottom", fontsize=5.3, color=C.INK2)
    ax.set_xticks(xs, ["E1"] + [k for t in T0S for k in ("E2", "E3")], fontsize=6.3)
    for i, t in enumerate(T0S):
        ax.text((xs[1 + 2 * i] + xs[2 + 2 * i]) / 2, -0.20, f"$T_0$ = {t} h", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=6.5)
    ax.set_yscale("log")
    ax.set_ylim(5e-3, 30)
    ax.set_ylabel("Wasted time (% of useful)\n(log scale)")
    ax.set_title("$\\rho$ = 0.9, all hosts", fontsize=8)
    ax.legend(handles=[Patch(color=C.POLICY_COLOR[k], label=C.POLICY_LABEL[k]) for k in ("E1", "E2", "E3")],
              loc="upper right", fontsize=6.2)
    fig.tight_layout()
    C.save(fig, P_OUT, "g09_wasted_time_all_policies_rho09")
    pd.DataFrame(rows).assign(rho="0.9").to_csv(ddir(P_OUT) / "g09_wasted_time_all_policies_rho09.csv", index=False)

    # G10 trade-off overhead vs lost work
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.6))
    rows = []
    for k, mk in [("E2", "o"), ("E3", "s")]:
        ox, _, _ = series(ps, k, "overhead_pct_of_useful")
        ly, llo, lhi = series(ps, k, "lost_work_h")
        ax.plot(ox, ly, "-", color=C.POLICY_COLOR[k], lw=1.0, zorder=2)
        ax.errorbar(ox, ly, yerr=[ly - llo, lhi - ly], fmt=mk, ms=4.5, color=C.POLICY_COLOR[k], mec="white", mew=0.6,
                    elinewidth=0.6, capsize=1.5, label=C.POLICY_LABEL[k], zorder=3)
        for t, a, b in zip(T0S, ox, ly):
            if k == "E2":
                ax.annotate(f"$T_0$ = {t} h", (a, b), xytext=(3, 6), textcoords="offset points", fontsize=6,
                            ha="left", va="bottom", color=C.INK2)
            rows.append({"policy": k, "T0_h": t, "overhead_pct_of_useful": a, "lost_work_h": b})
    e1 = C.getv(ps, "all", "E1_none", "lost_work_h")
    ax.axhline(e1, color=C.C_E1, ls="--", lw=1.2, label=f"E1 lost work ({e1:,.0f} h; 0 overhead)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Checkpoint overhead (% of useful compute, log scale)")
    ax.set_ylabel("Lost computation (h, log scale)")
    ax.grid(True, axis="both")
    ax.set_title("$\\rho$ = 0.9, all hosts; lower-left is better", fontsize=8)
    ax.legend(loc="lower left", fontsize=6.2)
    fig.tight_layout()
    C.save(fig, P_OUT, "g10_overhead_vs_lost_tradeoff_rho09")
    pd.DataFrame(rows).assign(rho="0.9").to_csv(ddir(P_OUT) / "g10_overhead_vs_lost_tradeoff_rho09.csv", index=False)

    simple_metric_fig("0.9", "checkpoints_per_job", "Checkpoints per job", P_OUT, "g11_checkpoints_per_job_rho09",
                      log=True, e1=False, label_fmt=lambda v: f"{v:.2f}")

    # G12 paired relative differences, both scenarios (separate files, never pooled)
    for rho in ("0.9", "1.0"):
        paired_forest(rho)

    # ======================= SATURATED rho = 1.0 =======================
    simple_metric_fig("1.0", "deadline_miss_pct", "Deadline miss rate (% of jobs)", S_OUT,
                      "g13_deadline_miss_vs_T0_rho10", label_fmt=lambda v: f"{v:.2f}" if v >= 0.01 else f"{v:.3f}",
                      e1fmt="{:.3f} %", title="$\\rho$ = 1.0 (saturated), all hosts")
    simple_metric_fig("1.0", "queue_mean_h_per_job", "Mean queueing delay (h per job)", S_OUT,
                      "g14_queueing_vs_T0_rho10", log=True, label_fmt=lambda v: f"{v:.2f}", e1fmt="{:.2f} h",
                      title="$\\rho$ = 1.0 (saturated), all hosts")
    simple_metric_fig("1.0", "lost_work_h", "Lost computation (h)", S_OUT, "g15_lost_work_vs_T0_rho10", log=True,
                      label_fmt=fmt_h, e1fmt="{:,.0f} h", title="$\\rho$ = 1.0 (saturated), all hosts")
    # G16 failing-host deadline misses, two scenarios side by side (separate panels)
    fig, axs = plt.subplots(1, 2, figsize=(C.DBL_W * 0.72, 2.3), sharey=True)
    rows = []
    for ax, rho, ttl in [(axs[0], "0.9", "(a) $\\rho$ = 0.9 (primary)"), (axs[1], "1.0", "(b) $\\rho$ = 1.0 (saturated)")]:
        r = grouped(ax, C.policy_summary(rho), "deadline_miss_pct", "failing",
                    label_fmt=lambda v: f"{v:.1f}", e1_label_fmt="{:.1f} %")
        rows += [dict(x, rho=rho) for x in r]
        ax.set_title(ttl, fontsize=8)
        ax.legend(loc="upper right", fontsize=6.2)
    axs[0].set_ylabel("Deadline miss rate on failing hosts (%)")
    fig.tight_layout()
    C.save(fig, S_OUT, "g16_failing_host_deadline_miss_both_rho")
    pd.DataFrame(rows).to_csv(ddir(S_OUT) / "g16_failing_host_deadline_miss_both_rho.csv", index=False)

    # ======================= RISK ANALYSIS =======================
    risk_graphs()


def paired_forest(rho):
    pc = C.paired(rho)
    out = P_OUT if rho == "0.9" else S_OUT
    metrics = [("checkpoint_overhead_h", "(a) Checkpoint overhead", True),
               ("lost_work_h", "(b) Lost computation", True),
               ("wasted_pct_of_useful", "(c) Total wasted time", True),
               ("deadline_miss_pct", "(d) Deadline miss rate", False)]
    fig, axs = plt.subplots(1, 4, figsize=(C.DBL_W, 1.9), sharey=True)
    rows = []
    ys = np.arange(len(T0S))[::-1]
    for ax, (m, ttl, rel) in zip(axs, metrics):
        for y, t in zip(ys, T0S):
            r = C.getpair(pc, "all", C.pol("E3", t), C.pol("E2", t), m)
            base = r.policy_b
            if rel:
                d, lo, hi = (100 * r.difference / base, 100 * r.ci_lo / base, 100 * r.ci_hi / base)
            else:
                d, lo, hi = r.difference, r.ci_lo, r.ci_hi
            ex = bool(r.ci_excludes_zero)
            ax.errorbar([d], [y], xerr=[[d - lo], [hi - d]], fmt="o", ms=4.2, color=C.INK, mfc=C.INK if ex else "white",
                        mec=C.INK, mew=0.9, elinewidth=1.0, capsize=1.8)
            rows.append({"rho": rho, "T0_h": t, "metric": m, "scale": "pct_of_E2" if rel else "percentage_points",
                         "E3": r.policy_a, "E2": base, "difference": r.difference, "ci_lo": r.ci_lo, "ci_hi": r.ci_hi,
                         "plotted_value": d, "plotted_lo": lo, "plotted_hi": hi, "ci_excludes_zero": bool(r.ci_excludes_zero)})
        ax.axvline(0, color=C.INK, lw=0.6)
        ax.set_title(ttl, fontsize=7.5)
        ax.set_xlabel("E3 vs E2 (% of E2)" if rel else "E3 $-$ E2 (pp)", fontsize=7)
        ax.grid(True, axis="x"); ax.grid(False, axis="y")
    axs[0].set_yticks(ys, [f"$T_0$ = {t} h" for t in T0S])
    fig.tight_layout(w_pad=0.6, rect=(0, 0, 1, 0.90))
    fig.text(0.5, 0.97, f"Paired E3 $-$ E2 differences, $\\rho$ = {rho}, all hosts (negative = E3 lower = favourable; "
             "95 % host-clustered bootstrap CIs; filled = CI excludes 0, open = CI includes 0)", fontsize=7.2,
             ha="center", va="top")
    stem = f"g12_paired_E3_vs_E2_rho{rho.replace('.', '')}"
    C.save(fig, out, stem)
    pd.DataFrame(rows).to_csv(ddir(out) / f"{stem}.csv", index=False)


def risk_graphs():
    d = ddir(R_OUT)
    # G17 tier occupancy (identical in both scenarios - asserted)
    occ = pd.read_csv(C.ANALYSIS["0.9"] / "tier_occupancy.csv")
    occ1 = pd.read_csv(C.ANALYSIS["1.0"] / "tier_occupancy.csv")
    assert occ.equals(occ1), "tier occupancy differs between scenarios"
    order = [("validation_design_target", "Validation target\n(May, by design)"), ("all", "All June hosts\n(110,848)"),
             ("non_failing", "Non-failing hosts\n(110,673)"), ("failing", "Failing hosts\n(175)")]
    fig, ax = plt.subplots(figsize=(C.COL_W, 1.9))
    for i, (key, lab) in enumerate(order[::-1]):
        r = occ[occ.hosts == key].iloc[0]
        left = 0
        for t in C.TIERS:
            v = float(r[t])
            ax.barh(i, v, left=left, height=0.62, color=C.TIER_COLOR[t], hatch=C.TIER_HATCH[t], edgecolor="white",
                    linewidth=0.8)
            if v >= 5:
                ax.text(left + v / 2, i, f"{v:.1f}", ha="center", va="center", fontsize=6.3, color=C.INK,
                        bbox=dict(boxstyle="square,pad=0.12", fc="white", ec="none", alpha=0.85))
            left += v
    ax.set_yticks(range(len(order)), [l for _, l in order[::-1]], fontsize=6.6)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of host-days (%), June days 1–30")
    ax.grid(True, axis="x"); ax.grid(False, axis="y")
    ax.legend(handles=[Patch(facecolor=C.TIER_COLOR[t], hatch=C.TIER_HATCH[t], edgecolor="white", label=t) for t in C.TIERS],
              loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, fontsize=6.5)
    fig.tight_layout()
    C.save(fig, R_OUT, "g17_tier_occupancy")
    occ.to_csv(d / "g17_tier_occupancy.csv", index=False)

    # G18 failure events by tier at failure (identical across policies & scenarios - asserted)
    fd = {rho: pd.read_csv(C.ANALYSIS[rho] / "failures_detail.csv") for rho in ("0.9", "1.0")}
    key = lambda df: df[df.run == "E1_none"].sort_values(["serial"])[["serial", "time", "tier_at_failure"]].reset_index(drop=True)
    base = key(fd["0.9"])
    for rho, df in fd.items():
        for run, g in df.groupby("run"):
            gg = g.sort_values("serial")[["serial", "time", "tier_at_failure"]].reset_index(drop=True)
            assert gg.equals(base), (rho, run)
    cnt = base.tier_at_failure.value_counts().reindex(C.TIERS)
    fig, ax = plt.subplots(figsize=(C.COL_W * 0.75, 1.9))
    for i, t in enumerate(C.TIERS):
        ax.bar(i, cnt[t], 0.6, color=C.TIER_COLOR[t], hatch=C.TIER_HATCH[t], edgecolor="white", linewidth=0.8)
        ax.text(i, cnt[t] + 2, f"{cnt[t]} ({100*cnt[t]/cnt.sum():.1f} %)", ha="center", va="bottom", fontsize=6.5)
    ax.set_xticks(range(3), C.TIERS)
    ax.set_ylabel("Failure events")
    ax.set_xlabel("Risk tier in force at the failure instant")
    ax.set_ylim(0, cnt.max() * 1.2)
    ax.set_title(f"All {cnt.sum()} June failures (same in every policy and $\\rho$)", fontsize=7.5)
    fig.tight_layout()
    C.save(fig, R_OUT, "g18_failures_by_tier")
    cnt.rename("failures").to_frame().to_csv(d / "g18_failures_by_tier.csv")

    # G19 lost computation by tier at failure, E2 vs E3 per T0, rho = 0.9
    df = fd["0.9"]
    lost = df.groupby(["run", "tier_at_failure"]).lost_h.sum().unstack().reindex(columns=C.TIERS).fillna(0)
    fig, axs = plt.subplots(1, 3, figsize=(C.DBL_W, 2.1))
    rows = []
    x = np.arange(len(T0S)); w = 0.38
    for ax, t in zip(axs, C.TIERS):
        for k, off in [("E2", -w / 2), ("E3", w / 2)]:
            v = np.array([lost.loc[C.pol(k, t0), t] for t0 in T0S])
            ax.bar(x + off, v, w, color=C.POLICY_COLOR[k], edgecolor="white", linewidth=0.8, label=C.POLICY_LABEL[k])
            for xi, vi in zip(x + off, v):
                ax.text(xi, vi * 1.12, f"{vi:,.0f}", ha="center", va="bottom", fontsize=5.3, color=C.INK2)
            rows += [{"tier_at_failure": t, "policy": k, "T0_h": t0, "lost_h": vi} for t0, vi in zip(T0S, v)]
        e1 = lost.loc["E1_none", t]
        ax.axhline(e1, color=C.C_E1, ls="--", lw=1.2, label="E1 No checkpointing")
        rows.append({"tier_at_failure": t, "policy": "E1", "T0_h": None, "lost_h": e1})
        ax.set_yscale("log"); ax.set_ylim(3, 2e4)
        ax.set_xticks(x, XL); ax.set_xlabel("Baseline interval $T_0$")
        ax.set_title(f"Failures in {t} tier (n = {cnt[t]})", fontsize=8)
    axs[0].set_ylabel("Lost computation (h, log scale)")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.03), fontsize=6.8)
    fig.suptitle("$\\rho$ = 0.9: lost computation grouped by the risk tier in force when the failure occurred", fontsize=8, y=1.0)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    C.save(fig, R_OUT, "g19_lost_work_by_tier_rho09")
    pd.DataFrame(rows).assign(rho="0.9").to_csv(d / "g19_lost_work_by_tier_rho09.csv", index=False)

    # G20 checkpoint overhead by tier, E2 vs E3, indexed to E2 total = 100 at each T0, rho = 0.9
    cb = pd.read_csv(C.ANALYSIS["0.9"] / "checkpoints_by_tier.csv")
    ov = cb.groupby(["run", "tier"]).overhead_h.sum().unstack().reindex(columns=C.TIERS).fillna(0)
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.5))
    rows = []
    w = 0.36
    for i, t0 in enumerate(T0S):
        e2tot = ov.loc[C.pol("E2", t0)].sum()
        for k, off in [("E2", -w / 2 - 0.02), ("E3", w / 2 + 0.02)]:
            bottom = 0
            for t in C.TIERS:
                v = 100 * ov.loc[C.pol(k, t0), t] / e2tot
                ax.bar(i + off, v, w, bottom=bottom, color=C.TIER_COLOR[t], hatch=C.TIER_HATCH[t], edgecolor="white",
                       linewidth=0.8)
                rows.append({"T0_h": t0, "policy": k, "tier": t, "overhead_h": ov.loc[C.pol(k, t0), t],
                             "index_E2_total_100": v})
                bottom += v
            ax.text(i + off, bottom + 1.5, k, ha="center", va="bottom", fontsize=6, color=C.INK)
            ax.text(i + off, -9, f"{bottom:.0f}", ha="center", va="top", fontsize=5.6, color=C.INK2)
    ax.set_xticks(range(len(T0S)), XL)
    ax.tick_params(axis="x", pad=11)
    ax.set_xlabel("Baseline interval $T_0$ (number under each bar = index total)")
    ax.set_ylabel("Checkpoint overhead\n(index, E2 total at same $T_0$ = 100)")
    ax.set_ylim(0, 125)
    ax.set_title("$\\rho$ = 0.9, all hosts: overhead split by risk tier at checkpoint", fontsize=7.5)
    ax.legend(handles=[Patch(facecolor=C.TIER_COLOR[t], hatch=C.TIER_HATCH[t], edgecolor="white", label=t) for t in C.TIERS],
              loc="upper center", bbox_to_anchor=(0.5, -0.33), ncol=3, fontsize=6.5)
    fig.tight_layout()
    C.save(fig, R_OUT, "g20_overhead_by_tier_rho09")
    pd.DataFrame(rows).assign(rho="0.9").to_csv(d / "g20_overhead_by_tier_rho09.csv", index=False)


if __name__ == "__main__":
    main()
