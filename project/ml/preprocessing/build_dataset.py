#!/usr/bin/env python
"""
Build the 7-day disk-failure prediction example files (no model training).

Pipeline
  1. labels.build_label_table()   - pass 1 over serial_number/failure only -> label codes
  2. day-by-day pass (pass 2)      - read raw SMART columns for day t, apply the 2019-06-17
                                     safeguard, compute past-only features from a buffer
                                     holding days t-7 .. t-1, attach labels, and write the
                                     train/test rows
  3. summaries                     - dataset_split_summary.csv, drive_heldout_folds.csv,
                                     feature_manifest.md, build_summary.json

Outputs (project/ml/processed/):
  train_chronological.csv.gz   features + metadata + label_primary + label_sensitivity
  test_chronological.csv.gz    (rows: primary-eligible examples; label_sensitivity is NaN where
                                the sensitivity outcome is unknown)
  train_sensitivity.csv.gz     key file: serial_number, date, fold, label_sensitivity for
  test_sensitivity.csv.gz      sensitivity-eligible rows (a strict subset of the primary rows)
  drive_heldout_folds.csv      serial_number -> fold (crc32 % 5)

Usage (from C:/Users/rushi/CC_project):
    python -I project/ml/preprocessing/build_dataset.py
"""
import gzip
import json
import os
import sys
import time
import zlib
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (ALTERED_FILE_DAMAGED_COLUMNS, ALTERED_FILE_DATE, FLOAT_FORMAT, GZIP_LEVEL,
                    HORIZON_DAYS, LABEL_COLUMNS, METADATA_COLUMNS, N_FOLDS, PARTIAL_ATTRIBUTES,
                    PROCESSED_DIR, PURGE_END, PURGE_START, QUALITY_EXCLUDED_SERIALS, RAW_COLUMNS,
                    TAIL_END, TAIL_START, TEST_END, TEST_START, TRAIN_END, TRAIN_START)
from features import build_features, feature_names
from io_utils import daily_files, read_daily
from labels import build_label_table, to_day


def split_of(date):
    if TRAIN_START <= date <= TRAIN_END:
        return "train"
    if PURGE_START <= date <= PURGE_END:
        return "purge"
    if TEST_START <= date <= TEST_END:
        return "test"
    if TAIL_START <= date <= TAIL_END:
        return "tail"
    raise ValueError(f"date outside configured periods: {date}")


def fold_of(serial: str) -> int:
    return zlib.crc32(str(serial).encode()) % N_FOLDS


def main():
    t0 = time.time()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    feats = feature_names()
    out_cols = METADATA_COLUMNS + feats + LABEL_COLUMNS

    # ------------------------------------------------------------------ pass 1: labels
    print("Pass 1: labels from serial_number/failure ...", flush=True)
    key, serials, serial_id = build_label_table()
    labels_by_day = {d: g.set_index("sid")[["label_primary", "label_sensitivity"]]
                     for d, g in key.groupby("day")}
    print(f"  {len(key):,} drive-days, {len(serials):,} drives ({time.time() - t0:.0f}s)", flush=True)

    # ------------------------------------------------------------------ pass 2: features
    handles = {
        "train": gzip.open(PROCESSED_DIR / "train_chronological.csv.gz", "wt", compresslevel=GZIP_LEVEL, newline=""),
        "test": gzip.open(PROCESSED_DIR / "test_chronological.csv.gz", "wt", compresslevel=GZIP_LEVEL, newline=""),
    }
    sens_handles = {
        "train": gzip.open(PROCESSED_DIR / "train_sensitivity.csv.gz", "wt", compresslevel=GZIP_LEVEL, newline=""),
        "test": gzip.open(PROCESSED_DIR / "test_sensitivity.csv.gz", "wt", compresslevel=GZIP_LEVEL, newline=""),
    }
    header_done = defaultdict(bool)
    counts = defaultdict(lambda: defaultdict(int))
    pos_drives = defaultdict(set)
    fold_counts = defaultdict(lambda: defaultdict(int))
    fold_pos_drives = defaultdict(set)
    buffer = {}
    june17 = {}

    for date, path in daily_files():
        day = to_day(date)
        split = split_of(date)
        raw = read_daily(path, ["serial_number", "model"] + RAW_COLUMNS)
        raw = raw[~raw["serial_number"].isin(QUALITY_EXCLUDED_SERIALS)].set_index("serial_number")
        assert raw.index.is_unique

        # "not reported" indicators are taken BEFORE the 2019-06-17 masking
        missing_flags = raw[[f"smart_{a}_raw" for a in PARTIAL_ATTRIBUTES]].isna()
        altered = date == ALTERED_FILE_DATE
        if altered:
            damaged = [c for c in ALTERED_FILE_DAMAGED_COLUMNS if c in RAW_COLUMNS]
            june17["masked_columns"] = damaged
            june17["not_read_damaged_columns"] = [c for c in ALTERED_FILE_DAMAGED_COLUMNS if c not in RAW_COLUMNS]
            june17["non_null_before_mask"] = {c: int(raw[c].notna().sum()) for c in damaged}
            raw.loc[:, damaged] = np.nan

        # buffer only ever holds days strictly before t when features are computed
        assert all(d < day for d in buffer)
        if split in ("train", "test"):
            X = build_features(raw[RAW_COLUMNS], buffer, day, missing_flags)
            sid = X.index.map(serial_id).to_numpy()
            lab = labels_by_day[day].reindex(sid)
            lp = lab["label_primary"].to_numpy()
            ls = lab["label_sensitivity"].to_numpy()
            keep = np.isin(lp, (0, 1))
            out = X.loc[keep].copy()
            out.insert(0, "serial_number", out.index)
            out.insert(1, "date", date.strftime("%Y-%m-%d"))
            out.insert(2, "model", raw.loc[out.index, "model"].to_numpy())
            out.insert(3, "fold", [fold_of(s) for s in out.index])
            out.insert(4, "source_file_altered", np.int8(altered))
            out["label_primary"] = lp[keep].astype(np.int8)
            sens = ls[keep].astype(float)
            sens[~np.isin(sens, (0, 1))] = np.nan     # sensitivity-unknown inside primary rows
            out["label_sensitivity"] = sens
            out = out[out_cols]
            out.to_csv(handles[split], index=False, header=not header_done[split],
                       float_format=FLOAT_FORMAT, lineterminator="\n")
            s_rows = out.loc[out["label_sensitivity"].notna(), ["serial_number", "date", "fold", "label_sensitivity"]]
            s_rows.astype({"label_sensitivity": "int8"}).to_csv(
                sens_handles[split], index=False, header=not header_done[split], lineterminator="\n")
            header_done[split] = True

            # ---- running counts ----
            c = counts[split]
            c["observation_rows"] += len(X)
            for code, name in ((1, "positive_rows"), (0, "negative_rows_primary"), (-1, "unknown_rows_primary"),
                               (-2, "excluded_failure_day_or_after")):
                c[name] += int((lp == code).sum())
            c["negative_rows_sensitivity"] += int((ls == 0).sum())
            c["unknown_rows_sensitivity"] += int((ls == -1).sum())
            c["unlabelled_rows"] += int(np.isnan(lp.astype(float)).sum())
            c["history_complete_rows"] += int(out["history_complete_7d"].sum())
            c["positive_rows_history_complete"] += int(out.loc[out["label_primary"] == 1, "history_complete_7d"].sum())
            c["rows_written"] += len(out)
            pos_drives[split].update(out.index[out["label_primary"] == 1])
            for k, g in out.groupby("fold"):
                fold_counts[(split, k)]["rows"] += len(g)
                fold_counts[(split, k)]["positive_rows"] += int((g["label_primary"] == 1).sum())
                fold_counts[(split, k)]["negative_rows_primary"] += int((g["label_primary"] == 0).sum())
                fold_pos_drives[(split, k)].update(g.index[g["label_primary"] == 1])
            if altered:
                june17["rows_written"] = len(out)
                june17["positive_rows"] = int((out["label_primary"] == 1).sum())
        else:
            counts[split]["observation_rows"] += len(raw)

        buffer[day] = raw[RAW_COLUMNS]
        for d in [d for d in buffer if d < day - 7]:
            del buffer[d]
        print(f"  {date.date()} [{split:<5}] rows={len(raw):,} written={counts[split]['rows_written']:,} "
              f"({time.time() - t0:.0f}s)", flush=True)

    for h in list(handles.values()) + list(sens_handles.values()):
        h.close()

    # ------------------------------------------------------------------ fold assignment file
    kept = [s for s in serials if s not in QUALITY_EXCLUDED_SERIALS]
    pd.DataFrame({"serial_number": kept, "fold": [fold_of(s) for s in kept]}).to_csv(
        PROCESSED_DIR / "drive_heldout_folds.csv", index=False)

    # ------------------------------------------------------------------ split summary
    rows = []
    for split in ("train", "purge", "test", "tail"):
        c = counts[split]
        rows.append({"configuration": "chronological", "split": split, "fold": "",
                     "observation_rows": c["observation_rows"],
                     "examples_written": c["rows_written"],
                     "positive_rows": c["positive_rows"], "positive_drives": len(pos_drives[split]),
                     "negative_rows_primary": c["negative_rows_primary"],
                     "unknown_rows_primary_excluded": c["unknown_rows_primary"],
                     "negative_rows_sensitivity": c["negative_rows_sensitivity"],
                     "unknown_rows_sensitivity_excluded": c["unknown_rows_sensitivity"],
                     "failure_day_or_after_excluded": c["excluded_failure_day_or_after"],
                     "history_complete_7d_rows": c["history_complete_rows"],
                     "positive_rows_history_complete_7d": c["positive_rows_history_complete"]})
    for k in range(N_FOLDS):
        tr, te = fold_counts[("train", k)], fold_counts[("test", k)]
        # drive-held-out fold k: train = train-period rows of drives NOT in k; test = test-period rows of drives in k
        tr_rows = sum(fold_counts[("train", j)]["rows"] for j in range(N_FOLDS) if j != k)
        tr_pos = sum(fold_counts[("train", j)]["positive_rows"] for j in range(N_FOLDS) if j != k)
        tr_neg = sum(fold_counts[("train", j)]["negative_rows_primary"] for j in range(N_FOLDS) if j != k)
        tr_pd = set().union(*[fold_pos_drives[("train", j)] for j in range(N_FOLDS) if j != k])
        rows.append({"configuration": "drive_heldout", "split": "train", "fold": k, "examples_written": tr_rows,
                     "positive_rows": tr_pos, "positive_drives": len(tr_pd), "negative_rows_primary": tr_neg})
        rows.append({"configuration": "drive_heldout", "split": "test", "fold": k, "examples_written": te["rows"],
                     "positive_rows": te["positive_rows"], "positive_drives": len(fold_pos_drives[("test", k)]),
                     "negative_rows_primary": te["negative_rows_primary"]})
    pd.DataFrame(rows).to_csv(PROCESSED_DIR / "dataset_split_summary.csv", index=False)

    summary = {"runtime_s": round(time.time() - t0, 1), "features": feats, "n_features": len(feats),
               "output_columns": out_cols, "counts": {k: dict(v) for k, v in counts.items()},
               "positive_drives": {k: len(v) for k, v in pos_drives.items()}, "june17": june17,
               "quality_excluded_serials": QUALITY_EXCLUDED_SERIALS, "horizon_days": HORIZON_DAYS,
               "file_sizes_bytes": {p.name: p.stat().st_size for p in PROCESSED_DIR.iterdir() if p.is_file()}}
    with open(PROCESSED_DIR / "build_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("features", "output_columns")}, indent=1, default=str))


if __name__ == "__main__":
    main()
