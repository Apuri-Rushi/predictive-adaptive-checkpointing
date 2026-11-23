#!/usr/bin/env python
"""
Phase 2 - baseline Random Forest for 7-day disk-failure prediction (Backblaze Q2 2019).

Steps
  1. Deterministic stratified sampling of the training file: all positives + 20:1 negatives.
  2. Internal time-based validation: fit on sampled rows 2019-04-01..05-03, purge 05-04..05-10,
     validate on ALL rows 2019-05-11..05-24 (natural prevalence). Small grid; select by PR-AUC.
  3. Prior correction of probabilities; calibration checked on the validation set.
     Decision threshold = max-F1 on validation, on the corrected-probability scale.
  4. Refit the selected configuration on the full training sample (04-01..05-24).
  5. Score the June test set ONCE (natural prevalence): row-level and drive-level metrics.

The June test period is never used for selection, thresholds or calibration.

Usage (from C:/Users/rushi/CC_project):
    python -I project/ml/training/train_random_forest.py
"""
import json
import os
import sys
import time
import zlib

import joblib
import numpy as np
import pandas as pd
import psutil
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import calibration_table, drive_metrics, max_f1_threshold, prior_correct, row_metrics
from rf_config import (BASE_PARAMS, CALIBRATION_BINS, CHUNK, FAILURE_SUMMARY, FEATURES, FIT_END, FIT_START,
                       FPR_POINTS, GRID, LABEL, MODELS_DIR, NEG_PER_POS, PERM_IMPORTANCE_NEG, PERM_REPEATS,
                       RESULTS_DIR, SEED, SELECTION_METRIC, TEST_FILE, THRESHOLD_RULE, TRAIN_FILE, VAL_END,
                       VAL_PURGE_END, VAL_PURGE_START, VAL_START)
from sampling import extract_sample, plan_sample

PROC = psutil.Process()
PEAK = {"rss_mb": 0.0}
T0 = time.time()
LOG_LINES = []


def log(msg):
    rss = PROC.memory_info().rss / 2**20
    PEAK["rss_mb"] = max(PEAK["rss_mb"], rss)
    line = f"[{time.time() - T0:7.0f}s | RSS {rss:6.0f} MB] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


def jdump(obj, path):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))


def stream_rows(path, date_lo, date_hi, extra=()):
    """Yield chunks (metadata, label, float32 feature matrix) for rows with date_lo <= date <= date_hi."""
    dtypes = {f: "float32" for f in FEATURES}
    dtypes.update({"serial_number": str, "date": str, "model": str, LABEL: "int8"})
    cols = ["serial_number", "date", "model", LABEL] + list(extra) + FEATURES
    lo, hi = date_lo.strftime("%Y-%m-%d"), date_hi.strftime("%Y-%m-%d")
    for ch in pd.read_csv(path, usecols=cols, dtype=dtypes, chunksize=CHUNK):
        m = (ch["date"] >= lo) & (ch["date"] <= hi)
        if m.any():
            ch = ch.loc[m]
            yield ch.drop(columns=FEATURES), ch[FEATURES].to_numpy(dtype=np.float32)


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log(f"python {sys.version.split()[0]}, scikit-learn {sklearn.__version__}, {len(FEATURES)} features, "
        f"{os.cpu_count()} CPUs")
    failure_dates = pd.read_csv(FAILURE_SUMMARY, dtype={"serial_number": str})
    failure_dates = dict(zip(failure_dates["serial_number"], pd.to_datetime(failure_dates["failure_date"])))

    # ------------------------------------------------------------ 1. sampling
    log("Step 1: stratified negative sampling (training period only)")
    mask, sinfo, by_date, by_model = plan_sample(log)
    S = extract_sample(mask, log)
    assert int((S[LABEL] == 1).sum()) == sinfo["positives_total"]
    assert int((S[LABEL] == 0).sum()) == sinfo["negatives_sampled"] == NEG_PER_POS * sinfo["positives_total"]
    beta_full = sinfo["negatives_sampled"] / sinfo["negatives_total"]
    by_date.to_csv(RESULTS_DIR / "sampling_distribution_by_date.csv", index_label="date")
    by_model.to_csv(RESULTS_DIR / "sampling_distribution_by_model.csv", index_label="model")

    # ------------------------------------------------------------ 2. internal validation
    fit = S[(S["date"] >= FIT_START) & (S["date"] <= FIT_END)]
    fit_dates = pd.date_range(FIT_START, FIT_END).strftime("%Y-%m-%d")
    neg_pop_fit = sum(sinfo["negatives_total_by_date"].get(d, 0) for d in fit_dates)
    neg_smp_fit = int((fit[LABEL] == 0).sum())
    beta_fit = neg_smp_fit / neg_pop_fit
    log(f"Step 2: internal fit set {FIT_START.date()}..{FIT_END.date()}: {int(fit[LABEL].sum()):,} positives, "
        f"{neg_smp_fit:,} negatives (beta_fit={beta_fit:.6g}); purge {VAL_PURGE_START.date()}..{VAL_PURGE_END.date()}; "
        f"validation {VAL_START.date()}..{VAL_END.date()} at natural prevalence")
    Xf, yf = fit[FEATURES].to_numpy(np.float32), fit[LABEL].to_numpy()
    models = []
    for g in GRID:
        t = time.time()
        m = RandomForestClassifier(**BASE_PARAMS, **g).fit(Xf, yf)
        models.append(m)
        log(f"  fitted {g} in {time.time() - t:.1f}s")

    val_meta, val_scores = [], [[] for _ in GRID]
    perm_X, perm_y = [], []
    for meta, X in stream_rows(TRAIN_FILE, VAL_START, VAL_END):
        val_meta.append(meta)
        for i, m in enumerate(models):
            val_scores[i].append(m.predict_proba(X)[:, 1].astype(np.float32))
        # permutation-importance subsample: all positives + ~1/30 of negatives (deterministic)
        k = np.fromiter((zlib.crc32(f"{SEED}|perm|{s}|{d}".encode()) % 30 == 0
                         for s, d in zip(meta["serial_number"], meta["date"])), bool, len(meta))
        keep = (meta[LABEL].to_numpy() == 1) | k
        perm_X.append(X[keep])
        perm_y.append(meta[LABEL].to_numpy()[keep])
    V = pd.concat(val_meta, ignore_index=True)
    V["date"] = pd.to_datetime(V["date"])
    yv = V[LABEL].to_numpy()
    log(f"  validation rows {len(V):,}, positives {int(yv.sum()):,} "
        f"({V.loc[yv == 1, 'serial_number'].nunique()} drives)")

    grid_rows = []
    for i, g in enumerate(GRID):
        s = np.concatenate(val_scores[i])
        p = prior_correct(s, beta_fit)
        r = row_metrics(yv, p, fpr_points=FPR_POINTS)
        grid_rows.append({**{k: ("None" if v is None else v) for k, v in g.items()}, **r})
    grid = pd.DataFrame(grid_rows)
    grid.to_csv(RESULTS_DIR / "validation_grid_results.csv", index=False)
    best_i = int(grid[SELECTION_METRIC].values.argmax())
    best = GRID[best_i]
    log(f"  selected {best} by validation {SELECTION_METRIC}={grid.loc[best_i, SELECTION_METRIC]:.4f}")

    pv = prior_correct(np.concatenate(val_scores[best_i]), beta_fit)
    thr, f1, prec, rec = max_f1_threshold(yv, pv)
    log(f"  threshold (max F1 on validation, corrected scale) = {thr:.6g}  F1={f1:.4f} P={prec:.4f} R={rec:.4f}")
    val_row = row_metrics(yv, pv, threshold=thr, fpr_points=FPR_POINTS)
    V["y"], V["p"] = yv, pv
    val_drive, val_drive_per = drive_metrics(V[["serial_number", "date", "y", "p"]], thr, failure_dates)
    cal_val = calibration_table(yv, pv, CALIBRATION_BINS)
    cal_val.to_csv(RESULTS_DIR / "calibration_validation.csv", index=False)
    raw_val = np.concatenate(val_scores[best_i])
    val_uncorrected = {"brier_uncorrected": float(np.mean((raw_val - yv) ** 2)),
                       "mean_uncorrected_score": float(raw_val.mean())}
    jdump({"selected_params": best, "beta_fit": beta_fit, "threshold": thr, "threshold_rule": THRESHOLD_RULE,
           "f1_at_threshold": f1, "row_level": val_row, "drive_level": val_drive, **val_uncorrected},
          RESULTS_DIR / "validation_metrics.json")
    val_drive_per.to_csv(RESULTS_DIR / "validation_failed_drives.csv", index=False)

    # permutation importance (validation subsample, selected internal model)
    PX, Py = np.concatenate(perm_X), np.concatenate(perm_y)
    log(f"  permutation importance on validation subsample: {len(Py):,} rows ({int(Py.sum())} positives)")
    pi = permutation_importance(models[best_i], PX, Py, scoring="average_precision", n_repeats=PERM_REPEATS,
                                random_state=SEED, n_jobs=1)
    del models, val_scores, PX, perm_X, val_meta
    log("  permutation importance done")

    # ------------------------------------------------------------ 3. final model
    log(f"Step 3: refit {best} on full training sample ({len(S):,} rows, beta={beta_full:.6g})")
    t = time.time()
    final = RandomForestClassifier(**BASE_PARAMS, **best).fit(S[FEATURES].to_numpy(np.float32), S[LABEL].to_numpy())
    fit_seconds = time.time() - t
    joblib.dump(final, MODELS_DIR / "random_forest_7d.joblib", compress=3)
    log(f"  final model fitted in {fit_seconds:.1f}s; saved "
        f"({(MODELS_DIR / 'random_forest_7d.joblib').stat().st_size / 2**20:.1f} MB)")
    imp = pd.DataFrame({"feature": FEATURES, "mdi_importance": final.feature_importances_,
                        "permutation_importance_mean": pi.importances_mean,
                        "permutation_importance_std": pi.importances_std})
    imp["mdi_rank"] = imp["mdi_importance"].rank(ascending=False, method="min").astype(int)
    imp["permutation_rank"] = imp["permutation_importance_mean"].rank(ascending=False, method="min").astype(int)
    imp.sort_values("mdi_rank").to_csv(RESULTS_DIR / "feature_importance.csv", index=False)

    # ------------------------------------------------------------ 4. single test evaluation
    log("Step 4: scoring the June test set once (natural prevalence)")
    test_meta, test_raw = [], []
    for meta, X in stream_rows(TEST_FILE, pd.Timestamp("2019-06-01"), pd.Timestamp("2019-06-23"),
                               extra=("label_sensitivity", "source_file_altered")):
        test_meta.append(meta)
        test_raw.append(final.predict_proba(X)[:, 1].astype(np.float32))
    T = pd.concat(test_meta, ignore_index=True)
    T["score_raw"] = np.concatenate(test_raw)
    T["p"] = prior_correct(T["score_raw"].to_numpy(), beta_full)
    T["y"] = T[LABEL].to_numpy()
    T["date"] = pd.to_datetime(T["date"])
    yt, pt = T["y"].to_numpy(), T["p"].to_numpy()
    log(f"  test rows {len(T):,}, positives {int(yt.sum()):,} ({T.loc[yt == 1, 'serial_number'].nunique()} drives)")
    test_row = row_metrics(yt, pt, threshold=thr, fpr_points=FPR_POINTS)
    test_drive, test_drive_per = drive_metrics(T[["serial_number", "date", "y", "p"]], thr, failure_dates)
    sens = T["label_sensitivity"].notna()
    test_row_sens = row_metrics(T.loc[sens, "label_sensitivity"].astype(int).to_numpy(), pt[sens.to_numpy()],
                                threshold=thr, fpr_points=FPR_POINTS)
    cal_test = calibration_table(yt, pt, CALIBRATION_BINS)
    cal_test.to_csv(RESULTS_DIR / "calibration_test.csv", index=False)
    by_model = []
    for mdl, g in T.groupby("model"):
        if g["y"].sum() >= 10:
            r = row_metrics(g["y"].to_numpy(), g["p"].to_numpy(), threshold=thr, fpr_points=FPR_POINTS)
            dsum, _ = drive_metrics(g[["serial_number", "date", "y", "p"]], thr, failure_dates)
            by_model.append({"model": mdl, "rows": r["rows"], "positive_rows": r["positives"],
                             "failed_drives": dsum["failed_drives"], "pr_auc": r["pr_auc"],
                             "recall_at_fpr_0.01": r["recall_at_fpr_0.01"],
                             "pct_failed_drives_detected": dsum["pct_failed_drives_detected"],
                             "false_alarms_per_1000_drive_days": dsum["false_alarms_per_1000_drive_days"]})
    pd.DataFrame(by_model).to_csv(RESULTS_DIR / "test_metrics_by_model.csv", index=False)
    test_drive_per.to_csv(RESULTS_DIR / "test_failed_drives.csv", index=False)
    T[["serial_number", "date", "model", "source_file_altered", "y", "score_raw", "p"]].rename(
        columns={"y": "label_primary", "p": "p_failure_7d_corrected"}).to_csv(
        RESULTS_DIR / "test_predictions.csv.gz", index=False, float_format="%.6g")
    j17 = T["source_file_altered"] == 1
    jdump({"row_level": test_row, "row_level_sensitivity_labels": test_row_sens, "drive_level": test_drive,
           "threshold": thr, "beta_full": beta_full,
           "brier_uncorrected": float(np.mean((T["score_raw"].to_numpy() - yt) ** 2)),
           "june17_rows": int(j17.sum()), "june17_positive_rows": int(T.loc[j17, "y"].sum())},
          RESULTS_DIR / "test_metrics.json")

    # ------------------------------------------------------------ 5. artifacts
    meta = {
        "created_utc": pd.Timestamp.utcnow().isoformat(), "sklearn_version": sklearn.__version__,
        "target": "P(drive records a failure on day t+1..t+7 | SMART history up to day t)",
        "features_in_order": FEATURES, "n_features": len(FEATURES),
        "model_params": {**BASE_PARAMS, **best}, "selection": {"metric": SELECTION_METRIC, "grid": GRID},
        "sampling": {k: v for k, v in sinfo.items() if not k.startswith("negatives_") or k in
                     ("negatives_total", "negatives_sampled")},
        "probability_correction": {"formula": "p = beta*s / (beta*s + 1 - s)", "beta": beta_full,
                                   "beta_internal_validation_model": beta_fit,
                                   "train_population_prevalence": sinfo["positives_total"] /
                                   (sinfo["positives_total"] + sinfo["negatives_total"]),
                                   "train_sample_prevalence": 1 / (1 + NEG_PER_POS)},
        "threshold": {"value_on_corrected_scale": thr, "rule": THRESHOLD_RULE,
                      "selected_on": f"validation {VAL_START.date()}..{VAL_END.date()}"},
        "internal_validation": {"fit": [str(FIT_START.date()), str(FIT_END.date())],
                                "purge": [str(VAL_PURGE_START.date()), str(VAL_PURGE_END.date())],
                                "validate": [str(VAL_START.date()), str(VAL_END.date())]},
        "final_fit_seconds": fit_seconds,
    }
    jdump(meta, MODELS_DIR / "random_forest_7d_metadata.json")
    with open(MODELS_DIR / "feature_order.txt", "w") as fh:
        fh.write("\n".join(FEATURES) + "\n")
    jdump(sinfo, RESULTS_DIR / "sampling_summary.json")
    log(f"done. peak RSS {PEAK['rss_mb']:.0f} MB, total {time.time() - T0:.0f}s")
    jdump({"peak_rss_mb": PEAK["rss_mb"], "runtime_s": time.time() - T0}, RESULTS_DIR / "run_resources.json")
    with open(RESULTS_DIR / "training_log.txt", "w") as fh:
        fh.write("\n".join(LOG_LINES) + "\n")


if __name__ == "__main__":
    main()
