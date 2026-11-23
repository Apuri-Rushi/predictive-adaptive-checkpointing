"""
Metrics and probability correction for the 7-day disk-failure model.

Prior correction (negatives downsampled, positives kept):
    Let beta = (# negatives in the training sample) / (# negatives in the population it was drawn from).
    Sampling only negatives multiplies the class odds by 1/beta, so for a model score s that
    estimates P(y=1 | x) under the sampled distribution:
        odds_true = beta * odds_sampled
        p_true    = beta * s / (beta * s + 1 - s)
    (Elkan 2001; Dal Pozzolo et al. 2015). This is exact only if s is itself calibrated on the
    sampled distribution; Random Forest scores generally are not, so calibration is CHECKED, not assumed.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             precision_recall_curve, roc_auc_score, roc_curve)


def prior_correct(s, beta):
    s = np.asarray(s, dtype=np.float64)
    return beta * s / (beta * s + 1.0 - s)


def recall_at_fpr(y, p, fpr_target):
    fpr, tpr, thr = roc_curve(y, p)
    ok = fpr <= fpr_target
    i = np.where(ok)[0][-1]
    return float(tpr[i]), float(thr[i]) if np.isfinite(thr[i]) else float("inf"), float(fpr[i])


def max_f1_threshold(y, p):
    prec, rec, thr = precision_recall_curve(y, p)
    f1 = 2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12)
    i = int(np.nanargmax(f1))
    return float(thr[i]), float(f1[i]), float(prec[i]), float(rec[i])


def calibration_table(y, p, n_bins=10):
    """Quantile-binned reliability table (bins contain equal numbers of rows)."""
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), n_bins, labels=False)
    t = df.groupby("bin").agg(rows=("y", "size"), p_min=("p", "min"), p_max=("p", "max"),
                              mean_predicted=("p", "mean"), observed_rate=("y", "mean"),
                              positives=("y", "sum")).reset_index()
    # top-score bins matter most at extreme imbalance: also add the top 1 % / 0.1 % slices
    extra = []
    for q in (0.99, 0.999):
        cut = df["p"].quantile(q)
        s = df[df["p"] >= cut]
        extra.append({"bin": f"top_{(1 - q) * 100:g}pct", "rows": len(s), "p_min": s["p"].min(),
                      "p_max": s["p"].max(), "mean_predicted": s["p"].mean(),
                      "observed_rate": s["y"].mean(), "positives": int(s["y"].sum())})
    return pd.concat([t, pd.DataFrame(extra)], ignore_index=True)


def row_metrics(y, p, threshold=None, fpr_points=(0.001, 0.01)):
    y = np.asarray(y).astype(int)
    out = {"rows": int(len(y)), "positives": int(y.sum()), "prevalence": float(y.mean()),
           "pr_auc": float(average_precision_score(y, p)), "roc_auc": float(roc_auc_score(y, p)),
           "brier": float(brier_score_loss(y, p)),
           "brier_reference_constant_prevalence": float(y.mean() * (1 - y.mean())),
           "mean_predicted": float(np.mean(p)), "observed_rate": float(y.mean())}
    for f in fpr_points:
        r, thr, fp = recall_at_fpr(y, p, f)
        out[f"recall_at_fpr_{f:g}"] = r
        out[f"threshold_at_fpr_{f:g}"] = thr
    if threshold is not None:
        pred = p >= threshold
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        out.update({"threshold": float(threshold), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
                    "precision": float(tp / max(tp + fp, 1)), "recall": float(tp / max(tp + fn, 1)),
                    "fpr": float(fp / max(fp + tn, 1)),
                    "false_alarms_per_1000_negative_drive_days": float(1000 * fp / max(fp + tn, 1))})
    return out


def drive_metrics(df, threshold, failure_dates):
    """Drive-level view. df: serial_number, date (Timestamp), y, p for one evaluation period.
    A failed drive (>= 1 positive row in the period) is DETECTED if any of its positive rows
    (days t with failure in t+1..t+7) has p >= threshold. Lead time = failure date - first alarm date."""
    pos = df[df["y"] == 1].copy()
    pos["alarm"] = pos["p"] >= threshold
    pos["fail_date"] = pos["serial_number"].map(failure_dates)
    rows = []
    for s, g in pos.groupby("serial_number"):
        al = g[g["alarm"]]
        rows.append({"serial_number": s, "failure_date": g["fail_date"].iloc[0].date(),
                     "positive_rows_in_period": len(g), "alarm_rows": len(al), "detected": bool(len(al)),
                     "first_alarm_date": al["date"].min().date() if len(al) else None,
                     "lead_time_days": int((g["fail_date"].iloc[0] - al["date"].min()).days) if len(al) else None,
                     "max_probability": float(g["p"].max())})
    per = pd.DataFrame(rows)
    neg = df[df["y"] == 0]
    never_failed = ~df["serial_number"].isin(pos["serial_number"])
    nf = df[never_failed]
    nf_alarmed = nf.loc[nf["p"] >= threshold, "serial_number"].nunique()
    lt = per.loc[per["detected"], "lead_time_days"]
    summary = {
        "failed_drives": int(len(per)),
        "failed_drives_detected": int(per["detected"].sum()),
        "pct_failed_drives_detected": float(100 * per["detected"].mean()) if len(per) else float("nan"),
        "lead_time_days_mean": float(lt.mean()) if len(lt) else None,
        "lead_time_days_median": float(lt.median()) if len(lt) else None,
        "lead_time_days_distribution": {int(k): int(v) for k, v in lt.value_counts().sort_index().items()},
        "false_alarm_rows": int((neg["p"] >= threshold).sum()),
        "negative_drive_days": int(len(neg)),
        "false_alarms_per_1000_drive_days": float(1000 * (neg["p"] >= threshold).mean()),
        "never_failed_drives": int(nf["serial_number"].nunique()),
        "never_failed_drives_with_any_alarm": int(nf_alarmed),
        "pct_never_failed_drives_with_any_alarm": float(100 * nf_alarmed / max(nf["serial_number"].nunique(), 1)),
    }
    return summary, per
