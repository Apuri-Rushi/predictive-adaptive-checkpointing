"""Architecture diagrams and flowcharts (Fig. 1-6), drawn programmatically as vector graphics.

Every label is taken from the implementation:
  ml/preprocessing/*, ml/training/*, ml/models/random_forest_7d_metadata.json
  cloudsim/research/src/ckpt/** (Policies, RiskTierClassifier, SimParams, CheckpointingBroker,
  FailureInjector, SimulationRunner, ExperimentRunner, DailyScoreTimeline, WorkloadGenerator)
"""
import matplotlib.patheffects as pe  # noqa: F401
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

import common as C
from common import plt

OUT = C.ASSETS / "architecture"
INK, INK2 = C.INK, C.INK2
ML_BG, ML_EC = "#eef4fc", "#9ec5f4"
SIM_BG, SIM_EC = "#fdf1eb", "#f3b493"
NATIVE_FC, NATIVE_EC = "#ececea", "#8c8b87"
CUSTOM_EC = C.C_E3
DATA_EC = "#52514e"


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def box(ax, cx, cy, w, h, title=None, body=None, fc="white", ec=INK2, lw=0.8, ls="-", fs=6.3, tfs=None,
        radius=0.05, align="center", tcolor=INK):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=2))
    tfs = tfs or fs + 0.5
    lines_t = title.split("\n") if title else []
    lines_b = body.split("\n") if body else []
    lh_t, lh_b = tfs * 1.22 / 72, fs * 1.22 / 72
    total = len(lines_t) * lh_t + len(lines_b) * lh_b + (0.03 if title and body else 0)
    y = cy + total / 2
    x = cx if align == "center" else cx - w / 2 + 0.07
    if title:
        ax.text(x, y, title, ha=align, va="top", fontsize=tfs, fontweight="bold", color=tcolor, zorder=3,
                linespacing=1.1)
        y -= len(lines_t) * lh_t + 0.03
    if body:
        ax.text(x, y, body, ha=align, va="top", fontsize=fs, color=INK, zorder=3, linespacing=1.12)


def diamond(ax, cx, cy, w, h, text, fs=6.3, fc="white", ec=INK2):
    ax.add_patch(Polygon([(cx - w / 2, cy), (cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2)], closed=True,
                         fc=fc, ec=ec, lw=0.8, zorder=2))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, fontweight="bold", zorder=3, linespacing=1.05)


def arrow(ax, pts, label=None, lpos=0.5, loff=(0, 0.06), ls="-", color=INK, lw=0.8, fs=5.8, head=True,
          lha="center", lcolor=INK2, seg=None):
    """Polyline arrow through pts (list of (x, y)); arrowhead on the last segment."""
    for i in range(len(pts) - 1):
        last = i == len(pts) - 2
        ax.add_patch(FancyArrowPatch(pts[i], pts[i + 1], arrowstyle="-|>,head_length=3.2,head_width=1.8"
                                     if (last and head) else "-", mutation_scale=1, shrinkA=0, shrinkB=0,
                                     color=color, lw=lw, ls=ls, zorder=1.5))
    if label:
        # put label on the chosen segment (default: the longest one)
        segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        if seg is not None:
            (x1, y1), (x2, y2) = segs[seg]
        else:
            (x1, y1), (x2, y2) = max(segs, key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
        ax.text(x1 + (x2 - x1) * lpos + loff[0], y1 + (y2 - y1) * lpos + loff[1], label, ha=lha, va="bottom",
                fontsize=fs, color=lcolor, zorder=4, style="italic",
                bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none", alpha=0.9))


def lane(ax, x, y, w, h, fc, ec, label, lx=0.08):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc=fc, ec=ec, lw=0.8,
                                zorder=0))
    ax.text(x + lx, y + h - 0.07, label, ha="left", va="top", fontsize=6.8, fontweight="bold", color=INK2)


# ===================================================================================== Fig. 1
def fig1():
    W, H = C.DBL_W, 3.55
    fig, ax = canvas(W, H)
    lane(ax, 0.05, 2.22, W - 0.1, 1.28, ML_BG, ML_EC,
         "OFFLINE: machine-learning pipeline (Python 3.10, scikit-learn 1.7.2) — trained once, no simulator involved")
    lane(ax, 0.05, 0.05, W - 0.1, 1.95, SIM_BG, SIM_EC,
         "ONLINE: trace-driven simulation (CloudSim 3.0.3 + custom engine, Java 8)", lx=0.75)
    bw, bh, y1 = 1.04, 0.78, 2.78
    xs = [0.64, 1.80, 2.96, 4.12, 5.28]
    top = [("Backblaze SMART\ndataset", "Q2 2019, 91 daily files\n9.83 M drive-days"),
           ("Data\npreprocessing", "cleaning, exclusions,\n7-day failure labels"),
           ("Feature\nengineering", "20 SMART attributes\n→ 128 temporal features"),
           ("Random Forest\ntraining", "train Apr 1–May 24\n20 : 1 negative sampling"),
           ("7-day failure-risk\nprediction", "prior-corrected score\np per drive-day")]
    for x, (t, b) in zip(xs, top):
        box(ax, x, y1, bw, bh, t, b, fs=5.9)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, [(a + bw / 2, y1), (b - bw / 2, y1)])
    box(ax, 6.47, y1, 1.08, bh, "Score trace", "test_predictions.csv.gz\nJune 1–23, one score\nper drive-day",
        ls="--", ec=DATA_EC, fs=5.7)
    arrow(ax, [(xs[-1] + bw / 2, y1), (6.47 - 0.54, y1)])

    bw2, y2 = 0.88, 0.95
    xb = [0.55 + i * 1.008 for i in range(7)]
    bot = [("Risk\nclassification", "LOW / MEDIUM / HIGH\nscore of day d used\nfrom day d+1"),
           ("Adaptive\ncheckpoint\nscheduler", "interval =\nf(tier, T₀)"),
           ("CloudSim\nsimulation\nenvironment", "datacenters, hosts,\nVMs, cloudlets"),
           ("Task\nexecution", "FIFO jobs run as\ncompute-segment\ncloudlets"),
           ("Failure\ndetection", "host failure at\ntrace time;\nD = 60 s"),
           ("Checkpoint\nrecovery", "spare host B = 120 s;\nrestore R = 300 s"),
           ("Performance\nevaluation", "overhead, lost work,\ndeadlines; paired\nbootstrap CIs")]
    for i, (x, (t, b)) in enumerate(zip(xb, bot)):
        box(ax, x, y2, bw2, 1.0, t, b, fs=5.5, tfs=6.0,
            ec=CUSTOM_EC if i in (0, 1, 3, 4, 5) else (NATIVE_EC if i == 2 else INK2),
            fc=NATIVE_FC if i == 2 else "white", lw=1.0)
    for a, b in zip(xb[:-1], xb[1:]):
        arrow(ax, [(a + bw2 / 2, y2), (b - bw2 / 2, y2)])
    # resume loop recovery -> task execution
    arrow(ax, [(xb[5], y2 - 0.5), (xb[5], 0.2), (xb[3], 0.2), (xb[3], y2 - 0.5)], label="resume task", lpos=0.5,
          loff=(0, 0.01))
    # score trace -> risk classification (labels never passed)
    arrow(ax, [(6.47, y1 - bh / 2), (6.47, 2.11), (xb[0], 2.11), (xb[0], y2 + 0.5)],
          label="daily scores only (failure labels are never passed to the simulator)", lpos=0.5, loff=(0, 0.015))
    # failure trace
    box(ax, xb[4], 1.74, 1.22, 0.3, None, "Failure trace: June failure dates\n(read only by the failure injector)",
        ls="--", ec=DATA_EC, fs=5.2)
    arrow(ax, [(xb[4], 1.59), (xb[4], y2 + 0.5)])
    # legend
    lx, ly = 0.18, 0.2
    for i, (fc, ec, ls, lab) in enumerate([("white", CUSTOM_EC, "-", "custom component"),
                                           (NATIVE_FC, NATIVE_EC, "-", "native CloudSim"),
                                           ("white", DATA_EC, "--", "data file / trace")]):
        ax.add_patch(Rectangle((lx + i * 0.95, ly - 0.05), 0.16, 0.1, fc=fc, ec=ec, ls=ls, lw=1.0))
        ax.text(lx + i * 0.95 + 0.21, ly, lab, fontsize=5.4, va="center", color=INK2)
    C.save(fig, OUT, "fig01_system_architecture")


# ===================================================================================== Fig. 2
def fig2():
    W, H = C.COL_W, 5.74
    fig, ax = canvas(W, H)
    steps = [
        ("Raw Backblaze daily monitoring records",
         "Q2 2019: 91 daily CSV files, 9,831,138 drive-days, 111,817 drives, 500 failures"),
        ("Data cleaning",
         "5 quality-excluded drives; damaged 2019-06-17 columns set to NaN;\nobservation day taken from the file name"),
        ("Failure-label generation (7-day horizon)",
         "positive: failure on day t+1 … t+7;  negative: drive still observed at t+7;\ncensored rows excluded"),
        ("Temporal feature engineering",
         "20 raw SMART attributes × {value, prev1, diff1, diff7, mean7, std7}\n+ 6 not-reported flags + 2 history counts = 128 features (records ≤ t)"),
        (None, None),
        ("Negative-class sampling",
         "all 1,842 positive rows + 36,840 negatives (20 : 1),\nstratified by date × drive model, seed 20190401"),
        ("Random Forest training",
         "300 trees, max depth 20, min leaf 1, √features, native NaN routing;\nselected by PR-AUC on internal validation (May 11–24)"),
        ("Prior-adjusted risk score",
         "p = βs / (βs + 1 − s),  β = 0.006415 (sampling rate of negatives)"),
        ("Risk classification",
         "LOW < 0.000234 ≤ MEDIUM < 0.001732 ≤ HIGH\n(validation P90 / P99; not tuned on June data)"),
    ]
    bw, x = 3.05, 1.84
    hs = [0.42, 0.52, 0.52, 0.52, 0.78, 0.52, 0.52, 0.42, 0.52]
    gap = 0.115
    y = H - 0.06
    centers = []
    for i, ((t, b), h) in enumerate(zip(steps, hs)):
        cy = y - h / 2
        is_sched = i == 8
        box(ax, x, cy, bw, h, t, b, fs=5.6, tfs=6.4, fc=ML_BG if i < 8 else "white",
            ec=ML_EC if i < 8 else CUSTOM_EC, lw=0.8 if i < 8 else 1.1)
        ax.add_patch(plt.Circle((0.16, cy), 0.11, fc=C.C_E2 if not is_sched else CUSTOM_EC, ec="none", zorder=3))
        ax.text(0.16, cy, str(i + 1), ha="center", va="center", fontsize=6.3, color="white", fontweight="bold",
                zorder=4)
        centers.append((cy, h))
        y -= h + gap
    for (c1, h1), (c2, h2) in zip(centers[:-1], centers[1:]):
        arrow(ax, [(x, c1 - h1 / 2), (x, c2 + h2 / 2)])
    # mini timeline inside step 5
    cy, h = centers[4]
    x0, x1 = x - bw / 2 + 0.12, x + bw / 2 - 0.12
    # dates: Apr 1 = day 0 ... Jun 23 = day 83  (Apr 30, May 31 days)
    span = 84.0
    segs = [(0, 54, "train Apr 1 – May 24", C.C_E2, "white"), (54, 61, "purge", C.C_E1, "white"),
            (61, 84, "test Jun 1 – 23", C.C_E3, "white")]
    ty = cy - 0.17
    for a, b, lab, col, tc in segs:
        xa, xb_ = x0 + (x1 - x0) * a / span, x0 + (x1 - x0) * b / span
        ax.add_patch(Rectangle((xa, ty - 0.085), xb_ - xa - 0.015, 0.17, fc=col, ec="none", zorder=3))
        ax.text((xa + xb_) / 2, ty, lab, ha="center", va="center", fontsize=5.2 if b - a > 10 else 4.8, color=tc,
                zorder=4)
    ax.text(x, cy + h / 2 - 0.07, "Chronological training / testing split", ha="center", va="top", fontsize=6.4,
            fontweight="bold", zorder=4)
    ax.text(x, cy + 0.02, "7-day purge: no training label window reaches the test period", ha="center",
            va="center", fontsize=5.6, zorder=4)
    # horizon annotation on step 3
    cy3, h3 = centers[2]
    ax.text(x + bw / 2 + 0.02, cy3, "H = 7 d", rotation=90, ha="left", va="center", fontsize=5.6, color=INK2)
    # separator: offline vs used by scheduler
    ax.text(W - 0.02, centers[8][0] + centers[8][1] / 2 + gap / 2, "used by the simulator ↓", ha="right",
            va="center", fontsize=5.2, color=CUSTOM_EC, style="italic")
    C.save(fig, OUT, "fig02_ml_pipeline")


# ===================================================================================== Fig. 3
def fig3():
    W, H = C.COL_W, 4.55
    fig, ax = canvas(W, H)
    cx = W / 2
    box(ax, cx, 4.27, 3.1, 0.42, "Random Forest output (offline)",
        "prior-corrected 7-day failure score p of the host's drive for day d − 1", ec=ML_EC, fc=ML_BG, fs=5.7)
    box(ax, cx, 3.6, 3.1, 0.42, "Risk tier classifier (fixed thresholds)",
        "applied at 00:00 of day d; no score yet → MEDIUM; spare host → MEDIUM", ec=CUSTOM_EC, lw=1.0, fs=5.7)
    arrow(ax, [(cx, 4.06), (cx, 3.81)], label="score only", loff=(0.36, -0.07), lha="left")
    xs = [0.62, cx, W - 0.62]
    tiers = [("LOW", "p < 0.000234"), ("MEDIUM", "0.000234 ≤ p < 0.001732"), ("HIGH", "p ≥ 0.001732")]
    rules = [("τ = 2.65 × T₀", "checkpoint less often"), ("τ = T₀", "same as fixed policy"),
             ("τ = T₀ / 4.9", "checkpoint more often")]
    for x, (t, rng), (r, note) in zip(xs, tiers, rules):
        arrow(ax, [(cx, 3.39), (cx, 3.22), (x, 3.22), (x, 3.06)])
        ax.add_patch(FancyBboxPatch((x - 0.5, 2.62), 1.0, 0.44, boxstyle="round,pad=0,rounding_size=0.04",
                                    fc=C.TIER_COLOR[t], ec="white", hatch=C.TIER_HATCH[t], lw=0.6, zorder=2,
                                    alpha=0.9))
        ax.text(x, 2.84, f"{t}\n{rng}", ha="center", va="center", fontsize=5.6, fontweight="bold", zorder=3,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.92))
        arrow(ax, [(x, 2.62), (x, 2.42)])
        box(ax, x, 2.2, 1.0, 0.44, r, note, ec=CUSTOM_EC, lw=1.0, fs=5.4, tfs=6.4)
        arrow(ax, [(x, 1.98), (x, 1.84), (cx, 1.84), (cx, 1.74)] if x != cx else [(x, 1.98), (x, 1.74)])
    box(ax, cx, 1.5, 3.1, 0.48, "Adaptive checkpoint scheduler (E3)",
        "next checkpoint due = last completed checkpoint (or job start) + τ;\n"
        "τ is re-evaluated at every 00:00 tier change; checkpoint = 300 s cloudlet", ec=CUSTOM_EC, lw=1.0, fs=5.5)
    # interval table
    ax.text(cx, 1.11, "Resulting intervals τ for each baseline T₀ (E2 fixed uses τ = T₀ for every tier)",
            ha="center", va="center", fontsize=5.6, style="italic", color=INK2)
    cols = ["T₀", "LOW", "MEDIUM", "HIGH"]
    rows = [(t, 2.65 * t, t, t / 4.9) for t in C.T0S]

    def fmt(hh):
        return f"{hh * 60:.1f} min" if hh < 1 else f"{hh:.2f} h".replace(".00 h", " h")
    tx = [0.55, 1.3, 2.15, 2.95]
    for j, c in enumerate(cols):
        ax.text(tx[j], 0.94, c, ha="center", va="center", fontsize=5.8, fontweight="bold")
    ax.plot([0.25, W - 0.25], [0.86, 0.86], color=INK2, lw=0.5)
    for i, (t, lo, me, hi) in enumerate(rows):
        yy = 0.76 - i * 0.15
        for j, v in enumerate([f"{t} h", fmt(lo), fmt(me), fmt(hi)]):
            ax.text(tx[j], yy, v, ha="center", va="center", fontsize=5.7)
    ax.plot([0.25, W - 0.25], [0.04, 0.04], color=INK2, lw=0.5)
    C.save(fig, OUT, "fig03_adaptive_checkpointing")


# ===================================================================================== Fig. 4
def fig4():
    W, H = C.DBL_W, 4.1
    fig, ax = canvas(W, H)
    # zones
    ax.add_patch(FancyBboxPatch((0.05, 0.62), 1.6, 3.43, boxstyle="round,pad=0,rounding_size=0.06", fc="white",
                                ec=DATA_EC, ls="--", lw=0.7, zorder=0))
    ax.text(0.12, 3.98, "Inputs (files)", fontsize=6.6, fontweight="bold", color=INK2, va="top")
    ax.add_patch(FancyBboxPatch((1.78, 0.62), 3.07, 3.43, boxstyle="round,pad=0,rounding_size=0.06", fc=SIM_BG,
                                ec=SIM_EC, lw=0.8, zorder=0))
    ax.text(1.85, 3.98, "Custom research code (package ckpt, Java 8)", fontsize=6.6, fontweight="bold",
            color=INK2, va="top")
    ax.add_patch(FancyBboxPatch((4.98, 0.62), 2.13, 3.43, boxstyle="round,pad=0,rounding_size=0.06", fc="#f6f6f4",
                                ec=NATIVE_EC, lw=0.8, zorder=0))
    ax.text(5.05, 3.98, "Native CloudSim 3.0.3 (unmodified jar)", fontsize=6.6, fontweight="bold", color=INK2,
            va="top")
    # inputs
    ins = [(3.35, "RF score trace", "test_predictions.csv.gz\n(serial, date, score)"),
           (2.45, "Failure trace", "drive_failure_summary.csv\n(June failure dates)"),
           (1.45, "Workload plan", "WorkloadGenerator: job list\nper host (identical for\nall 11 policies)")]
    for y, t, b in ins:
        box(ax, 0.85, y, 1.45, 0.66 if "Workload" in t else 0.56, t, b, ls="--", ec=DATA_EC, fs=5.4)
    # custom components
    box(ax, 2.52, 3.35, 1.3, 0.62, "RiskTraceLoader +\nDailyScoreTimeline", "score of day d effective from\nday d+1; carry-forward",
        ec=CUSTOM_EC, lw=1.0, fs=5.2, tfs=5.9)
    box(ax, 4.03, 3.35, 1.4, 0.62, "RiskTierClassifier +\nPolicies (E1/E2/E3)", "tier → interval τ",
        ec=CUSTOM_EC, lw=1.0, fs=5.3, tfs=5.9)
    box(ax, 2.52, 2.45, 1.3, 0.58, "FailureInjector\n(SimEntity)", "one timer per failure; the only\ncomponent that reads failure times",
        ec=CUSTOM_EC, lw=1.0, fs=5.0, tfs=5.9)
    box(ax, 3.85, 2.45, 1.0, 0.5, "Spare pool", "failures + 1 hosts;\nnever fail; MEDIUM",
        ec=CUSTOM_EC, lw=1.0, fs=5.0, tfs=5.9)
    box(ax, 3.32, 1.33, 2.9, 1.12, "CheckpointingBroker (extends DatacenterBroker)",
        "• FIFO job queue per host; arrivals at the planned submit times\n• job = chain of compute-segment cloudlets\n"
        "• checkpoint = 300 s cloudlet; committed work (checkpoint state) updated on completion\n"
        "• on failure: cancel; lost work = progress − committed\n• recovery: D + B, restore R, resume on a spare host\n"
        "• EventLog: per-job, checkpoint, failure and recovery records",
        ec=CUSTOM_EC, lw=1.1, fs=5.2, tfs=6.0, align="left")
    # native
    nat = [(3.45, "CloudSim engine", "CloudSim clock, SimEntity,\nSimEvent queue"),
           (2.72, "Datacenter entities", "50 hosts each;\nIdMappedVmAllocationPolicy (custom)"),
           (2.0, "Host", "1 PE, 1000 MIPS,\nVmSchedulerTimeShared"),
           (1.3, "VM (1 per host)", "1 PE, CloudletSchedulerSpaceShared")]
    for y, t, b in nat:
        box(ax, 6.05, y, 1.9, 0.52, t, b, fc=NATIVE_FC, ec=NATIVE_EC, fs=5.3, tfs=6.0)
    box(ax, 6.05, 0.83, 1.9, 0.3, "Cloudlet", "length (MI) = seconds × 1000", fc=NATIVE_FC, ec=NATIVE_EC, fs=5.1,
        tfs=5.8)
    for y1, y2 in [(3.19, 2.98), (2.46, 2.26), (1.74, 1.56), (1.04, 0.98)]:
        arrow(ax, [(6.05, y1), (6.05, y2)], head=True, color=INK2)
    # arrows inputs -> custom
    arrow(ax, [(1.575, 3.35), (1.87, 3.35)])
    arrow(ax, [(1.575, 2.45), (1.87, 2.45)])
    arrow(ax, [(1.575, 1.45), (1.87, 1.45)])
    ax.text(1.72, 1.5, "jobs", fontsize=5.4, style="italic", color=INK2, ha="center", va="bottom")
    arrow(ax, [(3.17, 3.35), (3.33, 3.35)])
    arrow(ax, [(4.55, 3.04), (4.55, 1.89)], label="τ per tier", seg=0, lpos=0.5, loff=(0.05, -0.04), lha="left")
    arrow(ax, [(3.85, 2.2), (3.85, 1.89)], label="spare VM", seg=0, lpos=0.4, loff=(0.05, -0.04), lha="left")
    arrow(ax, [(2.52, 2.16), (2.52, 1.89)], label="host s failed at t", seg=0, lpos=0.4, loff=(0.05, -0.04),
          lha="left")
    # broker <-> native
    arrow(ax, [(4.77, 1.62), (5.1, 1.62)], label="submit / cancel\ncloudlets", lpos=0.5, loff=(0, 0.02), fs=5.0)
    arrow(ax, [(5.1, 1.08), (4.77, 1.08)], label="cloudlet\nreturns", lpos=0.5, loff=(0, -0.24), fs=5.0)
    # abstraction strip
    box(ax, W / 2, 0.29, W - 0.1, 0.46, "Disk-to-host simulation abstraction",
        "1 Backblaze drive = 1 primary host = 1 VM = 1 PE (110,848 hosts in 56 shards). A recorded drive failure on day d becomes a "
        "host failure at d·86,400 s + crc32(\"fail|\"+serial) mod 86,400 s.\nThe running job moves to a spare host after "
        "D + B = 180 s. This is a modelling assumption: disk failures stand in for host failures; no real server failures are observed.",
        ec=INK2, fs=5.4, tfs=6.0, fc="white")
    # legend
    for i, (fc, ec, ls, lab) in enumerate([("white", CUSTOM_EC, "-", "custom"), (NATIVE_FC, NATIVE_EC, "-", "native CloudSim"),
                                           ("white", DATA_EC, "--", "input file")]):
        ax.add_patch(Rectangle((0.18, 0.95 - i * 0.12), 0.14, 0.08, fc=fc, ec=ec, ls=ls, lw=1.0))
        ax.text(0.37, 0.99 - i * 0.12, lab, fontsize=5.3, va="center", color=INK2)
    C.save(fig, OUT, "fig04_cloudsim_integration")


# ===================================================================================== Fig. 5
def fig5():
    W, H = C.DBL_W, 5.55
    fig, ax = canvas(W, H)
    sx, sw, bh = 2.7, 2.5, 0.46
    term = dict(radius=0.2)
    box(ax, sx, 5.2, sw, bh, None, "Job j arrives at its predetermined submit time\nand joins the host's FIFO queue",
        ec=INK, lw=1.0, fs=6.0, **term)
    diamond(ax, sx, 4.5, 1.5, 0.52, "Host free?")
    box(ax, sx, 3.8, sw, 0.36, None, "Start job (committed work = 0, progress = 0)", fs=6.0)
    box(ax, sx, 3.1, sw, bh, "Risk tier for the current day",
        "RF score of day d − 1 (carried forward); MEDIUM if no\nscore yet or if the job runs on a spare host", fs=5.8,
        ec=CUSTOM_EC, lw=1.0)
    box(ax, sx, 2.4, sw, bh, "Checkpoint interval τ = policy(tier, T₀)",
        "E1: no checkpoints   E2: τ = T₀   E3: 2.65T₀ / T₀ / T₀ ÷ 4.9", fs=5.8, ec=CUSTOM_EC, lw=1.0)
    box(ax, sx, 1.7, sw, bh, "Run compute segment (interruptible)",
        "until the earliest of: next checkpoint due,\nnext 00:00 (tier refresh), job end", fs=5.8)
    diamond(ax, sx, 1.0, 1.7, 0.52, "Segment\nended by?", fs=5.9)
    box(ax, sx, 0.3, sw, bh, None, "Job complete: on time if finish ≤ submit + 1.5 L,\notherwise late (all jobs run to completion)",
        ec=INK, lw=1.0, fs=6.0, **term)
    arrow(ax, [(sx, 5.2 - bh / 2), (sx, 4.76)])
    arrow(ax, [(sx, 4.24), (sx, 3.98)], label="Yes", loff=(0.12, -0.08), lha="left")
    ax.text(sx + 0.8, 4.52, "No: job waits in queue", fontsize=5.6, style="italic", color=INK2, va="center")
    arrow(ax, [(sx, 3.62), (sx, 3.1 + bh / 2)])
    arrow(ax, [(sx, 3.1 - bh / 2), (sx, 2.4 + bh / 2)])
    arrow(ax, [(sx, 2.4 - bh / 2), (sx, 1.7 + bh / 2)])
    arrow(ax, [(sx, 1.7 - bh / 2), (sx, 1.26)])
    arrow(ax, [(sx, 0.74), (sx, 0.3 + bh / 2)], label="job end", loff=(0.12, -0.07), lha="left")
    # midnight loop
    arrow(ax, [(sx - 0.85, 1.0), (0.78, 1.0), (0.78, 3.1), (sx - sw / 2, 3.1)], label="new day (00:00)",
          seg=0, lpos=0.5, loff=(0.0, 0.02))
    # completion frees host
    arrow(ax, [(sx - sw / 2, 0.3), (0.38, 0.3), (0.38, 4.5), (sx - 0.75, 4.5)], ls="--",
          label="host free → next job", seg=0, lpos=0.5, loff=(0.0, 0.02))
    # checkpoint
    jx = 4.78
    box(ax, jx, 1.0, 1.06, 0.66, "Write checkpoint", "C = 300 s cloudlet\n(interruptible); on\ncompletion: committed\n= progress",
        fs=5.3, tfs=6.0, ec=CUSTOM_EC, lw=1.0)
    arrow(ax, [(sx + 0.85, 1.0), (jx - 0.53, 1.0)], label="checkpoint due", loff=(0, 0.02))
    arrow(ax, [(jx - 0.36, 1.33), (jx - 0.36, 1.7), (sx + sw / 2, 1.7)])
    # failure branch
    fx, fw = 6.2, 1.66
    box(ax, fx, 5.2, fw, bh, "Host failure event", "at trace time (FailureInjector);\ninterrupts segment or write",
        ec="#e34948", lw=1.1, fs=5.6, **term)
    box(ax, fx, 4.5, fw, bh, None, "Cancel running cloudlet;\nlost work = progress − committed", fs=5.8)
    box(ax, fx, 3.8, fw, bh, None, "Failure detection and spare-host\nboot: D + B = 60 + 120 s", fs=5.8,
        ec=CUSTOM_EC, lw=1.0)
    diamond(ax, fx, 2.95, 1.45, 0.62, "Completed\ncheckpoint?", fs=5.9)
    box(ax, fx, 1.95, fw, bh, None, "Restore: R = 300 s;\nresume from committed work", fs=5.8, ec=CUSTOM_EC, lw=1.0)
    arrow(ax, [(fx, 5.2 - bh / 2), (fx, 4.5 + bh / 2)])
    arrow(ax, [(fx, 4.5 - bh / 2), (fx, 3.8 + bh / 2)])
    arrow(ax, [(fx, 3.8 - bh / 2), (fx, 3.26)])
    arrow(ax, [(fx, 2.64), (fx, 1.95 + bh / 2)], label="Yes", loff=(0.12, -0.05), lha="left")
    jn = 4.95
    arrow(ax, [(fx - 0.725, 2.95), (jn, 2.95)], head=False)
    ax.text((fx - 0.725 + jn) / 2 + 0.03, 2.99, "No: restart\nfrom zero", fontsize=5.4, style="italic", color=INK2,
            ha="center", va="bottom")
    arrow(ax, [(fx - fw / 2, 1.95), (jn, 1.95), (jn, 2.95)], head=False)
    arrow(ax, [(jn, 2.95), (jn, 3.1), (sx + sw / 2, 3.1)], label="continue on spare host", lpos=0.55, loff=(0, 0.02))
    ax.plot([jn], [2.95], "o", ms=2.5, color=INK, zorder=3)
    C.save(fig, OUT, "fig05_execution_flow")


# ===================================================================================== Fig. 6
def fig6():
    W, H = C.DBL_W, 3.62
    fig, ax = canvas(W, H)
    # scenario band
    ax.add_patch(FancyBboxPatch((1.95, 0.72), 2.55, 2.85, boxstyle="round,pad=0,rounding_size=0.06", fc=SIM_BG,
                                ec=SIM_EC, lw=0.8, zorder=0))
    ax.text(3.225, 3.5, "11 policy runs per shard (56 shards, 110,848 hosts)", ha="center", va="top", fontsize=6.4,
            fontweight="bold", color=INK2)
    # inputs
    ins = [(2.95, "Common workload", "per shard and scenario: jobs of\n24 / 72 / 168 h (p = 0.5 / 0.3 / 0.2),\n"
                                       "submit spacing L / ρ, 30-day window,\ndeadline = submit + 1.5 L"),
           (1.95, "Common failure trace", "175 June drive failures;\nidentical times in every run"),
           (1.15, "Common risk trace", "RF scores, June 1–23;\nidentical in every run")]
    for y, t, b in ins:
        box(ax, 0.95, y, 1.72, 0.78 if "workload" in t else 0.5, t, b, ls="--", ec=DATA_EC, fs=5.5)
        arrow(ax, [(1.81, y), (1.95, y)])
    pols = [(3.05, "E1", "No checkpointing", "1 run; failure → restart from zero"),
            (2.2, "E2", "Fixed-interval checkpointing", "τ = T₀ for T₀ = 1, 4, 12, 24, 72 h\n5 runs"),
            (1.22, "E3", "RF-based adaptive checkpointing", "LOW 2.65T₀ · MEDIUM T₀ · HIGH T₀ / 4.9\nsame 5 T₀ values, 5 runs")]
    for y, k, t, b in pols:
        box(ax, 3.225, y, 2.3, 0.6 if k != "E1" else 0.46, f"{k}: {t}", b, ec=C.POLICY_COLOR[k], lw=1.6, fs=5.6,
            tfs=6.2)
    # outputs
    box(ax, 5.85, 2.75, 2.35, 1.18, "Metrics (per job and per host)",
        "• deadline miss rate (% of jobs)\n• lost computation (h)\n• checkpoint overhead (h, % of useful compute)\n"
        "• wasted time (% of useful compute)\n• mean queueing delay (h per job)\n• checkpoints per job; recovery time (h)",
        fs=5.5, tfs=6.2, align="left")
    box(ax, 5.85, 1.42, 2.35, 0.86, "Paired statistical comparison",
        "host-clustered Poisson bootstrap, B = 2,000,\nseed 20190601, percentile 95 % CIs;\n"
        "E3 − E2 at equal T₀ and E2/E3 − E1;\nstrata: all / failing / non-failing hosts", fs=5.5, tfs=6.2, align="left")
    arrow(ax, [(4.5, 2.75), (5.85 - 1.175, 2.75)], label="records", loff=(0, 0.02))
    arrow(ax, [(5.85, 2.75 - 0.59), (5.85, 1.42 + 0.43)])
    # scenarios strip
    box(ax, 2.0, 0.33, 3.3, 0.5, "Scenario ρ = 0.9 (primary)",
        "10 % nominal idle slack; 1,141,653 jobs", ec=INK, lw=1.0, fs=5.8, tfs=6.4)
    box(ax, 5.35, 0.33, 3.3, 0.5, "Scenario ρ = 1.0 (saturated sensitivity)",
        "back-to-back arrivals, no slack; 1,259,916 jobs", ec=INK, lw=1.0, fs=5.8, tfs=6.4)
    ax.text(W / 2, 0.64, "The whole experiment above is run separately for each scenario (different workloads); "
            "results are compared only within a scenario, never pooled.", ha="center", va="center", fontsize=5.6,
            style="italic", color=INK2)
    C.save(fig, OUT, "fig06_experimental_design")


if __name__ == "__main__":
    C.apply_style()
    plt.rcParams["axes.grid"] = False
    for f in (fig1, fig2, fig3, fig4, fig5, fig6):
        f()
    print("diagrams done")
