"""Random Forest evaluation graphs (G01-G05), computed from the saved June test predictions.

Sources (read-only):
  ml/results/model_evaluation/test_predictions.csv.gz  (label_primary, p_failure_7d_corrected)
  ml/results/model_evaluation/test_metrics.json        (threshold, confusion counts - cross-checked)
  ml/results/model_evaluation/feature_importance.csv
  cloudsim/research/src/ckpt/policy/RiskTierClassifier.java (tier boundaries, copied as constants below)
"""
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from sklearn.metrics import (average_precision_score, confusion_matrix, precision_recall_curve,
                             roc_auc_score, roc_curve)

import common as C
from common import plt

OUT = C.ASSETS / "graphs" / "random_forest"
DATA = OUT / "data"
LOW_UPPER, HIGH_LOWER = 0.000234, 0.001732      # RiskTierClassifier.APPROVED_*


def main():
    C.apply_style()
    DATA.mkdir(parents=True, exist_ok=True)
    tm = C.load_json(C.MLEVAL / "test_metrics.json")["row_level"]
    thr = tm["threshold"]
    d = pd.read_csv(C.MLEVAL / "test_predictions.csv.gz", usecols=["label_primary", "p_failure_7d_corrected"])
    y = d["label_primary"].to_numpy()
    s = d["p_failure_7d_corrected"].to_numpy()
    prev = y.mean()
    auc, ap = roc_auc_score(y, s), average_precision_score(y, s)
    checks = {"rows": len(y), "positives": int(y.sum()), "roc_auc_recomputed": auc, "pr_auc_recomputed": ap,
              "roc_auc_reported": tm["roc_auc"], "pr_auc_reported": tm["pr_auc"]}

    # ---------------- G01 ROC (linear + log-FPR panel)
    fpr, tpr, _ = roc_curve(y, s)
    keep = np.unique(np.concatenate([np.linspace(0, len(fpr) - 1, 4000).astype(int),
                                     np.searchsorted(fpr, np.logspace(-6, 0, 400))]).clip(0, len(fpr) - 1))
    pd.DataFrame({"fpr": fpr[keep], "tpr": tpr[keep]}).to_csv(DATA / "g01_roc_curve_points.csv", index=False)
    pts = [(0.001, tm["recall_at_fpr_0.001"], "0.1 % FPR"), (0.01, tm["recall_at_fpr_0.01"], "1 % FPR")]
    fig, axs = plt.subplots(1, 2, figsize=(C.COL_W, 2.1))
    for ax, logx in zip(axs, [False, True]):
        ax.plot(fpr, tpr, color=C.C_E2, lw=1.5, label=f"Random Forest (AUC = {auc:.3f})")
        ax.plot([1e-6, 1], [1e-6, 1], color=C.INK2, lw=0.8, ls="--", label="Chance")
        for x, r, lab in pts:
            ax.plot([x], [r], "o", ms=4, color=C.INK, mec="white", mew=0.8, zorder=5)
        ax.set_ylim(0, 1)
        if not logx:
            ax.set_ylabel("True positive rate (recall)")
        ax.grid(True, axis="both")
        if logx:
            ax.set_xscale("log")
            ax.set_xlim(1e-5, 1)
            ax.set_xlabel("FPR (log scale)")
            for x, r, lab in pts:
                ax.annotate(f"{lab}:\nrecall {100*r:.1f} %", (x, r), xytext=(5, -3), textcoords="offset points",
                            ha="left", va="top", fontsize=6)
            ax.set_title("(b) Low-FPR region", fontsize=8)
        else:
            ax.set_xlim(0, 1)
            ax.set_xlabel("False positive rate")
            ax.set_title("(a) Full ROC", fontsize=8)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, fontsize=6.5, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(w_pad=0.8, rect=(0, 0.08, 1, 1))
    C.save(fig, OUT, "g01_rf_roc_curve")

    # ---------------- G02 Precision-recall
    prec, rec, _ = precision_recall_curve(y, s)
    keep = np.unique(np.linspace(0, len(prec) - 1, 5000).astype(int))
    pd.DataFrame({"recall": rec[keep], "precision": prec[keep]}).to_csv(DATA / "g02_pr_curve_points.csv", index=False)
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.3))
    ax.plot(rec, prec, color=C.C_E2, lw=1.5, label=f"Random Forest (PR-AUC = {ap:.4f})")
    ax.axhline(prev, color=C.INK2, lw=0.8, ls="--", label=f"Chance = prevalence ({100*prev:.3f} %)")
    ax.plot([tm["recall"]], [tm["precision"]], "o", ms=5, color=C.INK, mec="white", mew=0.8, zorder=5)
    ax.annotate(f"Selected threshold {thr:.5f}\nprecision {100*tm['precision']:.1f} %, recall {100*tm['recall']:.1f} %",
                (tm["recall"], tm["precision"]), xytext=(-10, -48), textcoords="offset points", fontsize=6.5,
                arrowprops=dict(arrowstyle="-", color=C.INK2, lw=0.6))
    ax.set_yscale("log")
    ax.set_ylim(1e-4, 1)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision (log scale)")
    ax.grid(True, axis="both")
    ax.legend(loc="upper right", fontsize=6.5)
    fig.tight_layout()
    C.save(fig, OUT, "g02_rf_precision_recall_curve")

    # ---------------- G03 Confusion matrix at the validation-selected threshold
    tn, fp, fn, tp = confusion_matrix(y, (s >= thr).astype(int), labels=[0, 1]).ravel()
    checks.update({"cm_recomputed": [int(tp), int(fp), int(fn), int(tn)], "cm_reported": [tm["tp"], tm["fp"], tm["fn"], tm["tn"]]})
    cm = np.array([[tp, fn], [fp, tn]])
    rate = cm / cm.sum(axis=1, keepdims=True)
    pd.DataFrame({"actual": ["fails_within_7d", "fails_within_7d", "no_failure_7d", "no_failure_7d"],
                  "predicted": ["fail", "ok", "fail", "ok"], "count": cm.ravel(),
                  "row_pct": 100 * rate.ravel()}).to_csv(DATA / "g03_confusion_matrix.csv", index=False)
    fig, ax = plt.subplots(figsize=(C.COL_W * 0.78, 2.0))
    cmap = plt.get_cmap("Blues")
    ax.imshow(rate, cmap=cmap, vmin=0, vmax=1.15)
    names = [["TP", "FN"], ["FP", "TN"]]
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{names[i][j]} = {cm[i, j]:,}\n({100*rate[i, j]:.2f} % of row)", ha="center", va="center",
                    fontsize=7, color="white" if rate[i, j] > 0.6 else C.INK)
    ax.set_xticks([0, 1], ["Predicted\nfailure", "Predicted\nno failure"])
    ax.set_yticks([0, 1], ["Fails within\n7 days", "Does not fail\nwithin 7 days"])
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    C.save(fig, OUT, "g03_rf_confusion_matrix")

    # ---------------- G04 Score distribution, failing vs non-failing rows (row-level 7-day label)
    bins = np.logspace(np.log10(max(s.min(), 1e-6)), 0, 70)
    hn, _ = np.histogram(s[y == 0], bins=bins)
    hp, _ = np.histogram(s[y == 1], bins=bins)
    pd.DataFrame({"bin_lo": bins[:-1], "bin_hi": bins[1:], "neg_count": hn, "pos_count": hp,
                  "neg_share": hn / hn.sum(), "pos_share": hp / hp.sum()}).to_csv(DATA / "g04_score_histogram.csv", index=False)
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.2))
    ax.stairs(100 * hn / hn.sum(), bins, color=C.C_E2, lw=1.4, label=f"No failure within 7 days (n = {int((y==0).sum()):,})")
    ax.stairs(100 * hp / hp.sum(), bins, color=C.C_E3, lw=1.4, label=f"Failure within 7 days (n = {int(y.sum()):,})")
    ymax = ax.get_ylim()[1]
    for x, lab, yf in [(LOW_UPPER, "LOW / MEDIUM\n0.000234", 0.97), (HIGH_LOWER, "MEDIUM / HIGH\n0.001732", 0.80),
                       (thr, "Alarm threshold\n0.01368", 0.63)]:
        ax.axvline(x, color=C.INK2, lw=0.7, ls=":")
        ax.text(x * 1.12, ymax * yf, lab, fontsize=5.8, va="top", color=C.INK2)
    ax.set_xscale("log")
    ax.set_xlabel("Prior-corrected 7-day failure score (log scale)")
    ax.set_ylabel("Share of class (%)")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.28), fontsize=6.5, ncol=1)
    fig.tight_layout()
    C.save(fig, OUT, "g04_rf_score_distribution")

    # ---------------- G05 Feature importance (top 15, both rankings)
    fi = pd.read_csv(C.MLEVAL / "feature_importance.csv")
    top_mdi = fi.sort_values("mdi_importance", ascending=False).head(15)
    top_perm = fi.sort_values("permutation_importance_mean", ascending=False).head(15)
    top_mdi.to_csv(DATA / "g05_top15_mdi.csv", index=False)
    top_perm.to_csv(DATA / "g05_top15_permutation.csv", index=False)
    fig, axs = plt.subplots(1, 2, figsize=(C.DBL_W, 2.6))
    for ax, df, col, err, title, xl in [
        (axs[0], top_mdi, "mdi_importance", None, "(a) Impurity importance (MDI), final model", "Mean decrease in impurity"),
        (axs[1], top_perm, "permutation_importance_mean", "permutation_importance_std",
         "(b) Permutation importance, validation model", "Mean decrease in average precision")]:
        yy = np.arange(len(df))[::-1]
        ax.barh(yy, df[col], color=C.C_E2, height=0.7, xerr=None if err is None else df[err],
                error_kw=dict(lw=0.6, capsize=1.5, ecolor=C.INK2))
        ax.set_yticks(yy, df["feature"].str.replace("_raw", "", regex=False).str.replace("smart_", "SMART ", regex=False))
        ax.set_title(title, fontsize=8)
        ax.set_xlabel(xl)
        ax.grid(True, axis="x")
        ax.grid(False, axis="y")
    fig.tight_layout(w_pad=2)
    C.save(fig, OUT, "g05_rf_feature_importance")

    pd.Series(checks).to_json(DATA / "rf_recompute_checks.json", indent=1)
    print(checks)


if __name__ == "__main__":
    main()
