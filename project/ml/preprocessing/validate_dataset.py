#!/usr/bin/env python
"""
Independent quality assertions on the built 7-day dataset, plus report generation.

Reads the output files back (streamed in chunks) and checks them against the raw CSVs
and the approved methodology counts. Writes:
    project/ml/processed/validation_results.json
    project/ml/processed/feature_manifest.md
    project/ml/processed/target_generation_report.md

Usage (from C:/Users/rushi/CC_project):
    python -I project/ml/preprocessing/validate_dataset.py
"""
import json
import os
import sys
import zlib
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (ALTERED_FILE_DATE, ATTRIBUTES, CORE_ATTRIBUTES, HORIZON_DAYS, LABEL_COLUMNS,
                    METADATA_COLUMNS, METHODOLOGY_COUNTS, N_FOLDS, PARTIAL_ATTRIBUTES, PROCESSED_DIR,
                    QUALITY_EXCLUDED_SERIALS, RAW_COLUMNS, ROLL_WINDOW, TEST_END, TEST_START,
                    TRAIN_END, TRAIN_START)
from features import feature_names
from io_utils import daily_files, read_daily

FORBIDDEN_FEATURES = {"serial_number", "date", "failure", "source_file_altered", "capacity_bytes",
                      "model", "fold", "label_primary", "label_sensitivity", "day_of_year"}
MASKED = ["smart_7_raw", "smart_188_raw", "smart_240_raw", "smart_241_raw", "smart_242_raw"]
SAMPLE_FAILED, SAMPLE_OTHER = 80, 220
CHUNK = 400_000
results = {}


def check(name, ok, detail=""):
    results[name] = {"pass": bool(ok), "detail": detail}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)


def stream(name, usecols=None):
    return pd.read_csv(PROCESSED_DIR / name, usecols=usecols, chunksize=CHUNK, low_memory=False)


def main():
    summary = json.load(open(PROCESSED_DIR / "build_summary.json"))
    feats = summary["features"]
    fds = pd.read_csv(PROCESSED_DIR.parent / "results" / "dataset_audit_revalidation" / "drive_failure_summary.csv")
    fail_date = dict(zip(fds["serial_number"], pd.to_datetime(fds["failure_date"])))

    # ---------------------------------------------------------------- 1. schema / feature matrix
    check("feature list matches features.feature_names()", feats == feature_names(), f"{len(feats)} features")
    bad = sorted(FORBIDDEN_FEATURES & set(feats))
    check("no identifier/label/date/source-flag/capacity column among features", not bad, str(bad))
    for split in ("train", "test"):
        hdr = pd.read_csv(PROCESSED_DIR / f"{split}_chronological.csv.gz", nrows=0).columns.tolist()
        check(f"{split}: columns = metadata + features + labels", hdr == METADATA_COLUMNS + feats + LABEL_COLUMNS)

    # ---------------------------------------------------------------- sample for independent recomputation
    # chosen BEFORE streaming so only these drives' rows are kept in memory
    rng = np.random.default_rng(20190401)
    failed_pool = sorted(set(fds["serial_number"]) - set(QUALITY_EXCLUDED_SERIALS))
    folds_df = pd.read_csv(PROCESSED_DIR / "drive_heldout_folds.csv")
    other_pool = folds_df.loc[~folds_df["serial_number"].isin(failed_pool), "serial_number"].to_numpy()
    sample = set(rng.choice(failed_pool, size=SAMPLE_FAILED, replace=False)) | \
        set(rng.choice(other_pool, size=SAMPLE_OTHER, replace=False))

    # ---------------------------------------------------------------- 2. stream outputs: counts & row rules
    counts, pos_drives, serial_fold = {}, defaultdict(set), {}
    fold_conflicts, sample_rows = 0, []
    excl_found = set()
    stats = defaultdict(int)
    for split, lo, hi in (("train", TRAIN_START, TRAIN_END), ("test", TEST_START, TEST_END)):
        c = defaultdict(int)
        dmin, dmax = pd.Timestamp.max, pd.Timestamp.min
        for ch in stream(f"{split}_chronological.csv.gz"):
            d = pd.to_datetime(ch["date"])
            dmin, dmax = min(dmin, d.min()), max(dmax, d.max())
            c["rows"] += len(ch)
            c["pos"] += int((ch["label_primary"] == 1).sum())
            c["neg"] += int((ch["label_primary"] == 0).sum())
            c["sens_neg"] += int((ch["label_sensitivity"] == 0).sum())
            c["sens_pos"] += int((ch["label_sensitivity"] == 1).sum())
            c["sens_unknown"] += int(ch["label_sensitivity"].isna().sum())
            c["label_primary_invalid"] += int((~ch["label_primary"].isin([0, 1])).sum())
            c["pos_with_sens_not_1"] += int(((ch["label_primary"] == 1) & (ch["label_sensitivity"] != 1)).sum())
            pos_drives[split].update(ch.loc[ch["label_primary"] == 1, "serial_number"])
            excl_found.update(set(ch["serial_number"]) & set(QUALITY_EXCLUDED_SERIALS))
            # fold consistency
            exp = ch["serial_number"].map(lambda s: zlib.crc32(str(s).encode()) % N_FOLDS)
            c["fold_mismatch"] += int((exp != ch["fold"]).sum())
            for s, f in zip(ch["serial_number"].to_numpy(), ch["fold"].to_numpy()):
                if serial_fold.setdefault(s, f) != f:
                    fold_conflicts += 1
            # failure-day / post-failure / label-rule checks against the audit failure dates
            fd = ch["serial_number"].map(fail_date)
            has = fd.notna()
            gap = (fd - d).dt.days
            c["rows_on_or_after_failure"] += int((has & (gap <= 0)).sum())
            c["pos_outside_1_7"] += int(((ch["label_primary"] == 1) & ~(has & gap.between(1, HORIZON_DAYS))).sum())
            c["neg_with_failure_within_7"] += int(((ch["label_primary"] == 0) & has & (gap <= HORIZON_DAYS)).sum())
            # missing-value conventions
            c["hist_flag_inconsistent"] += int(((ch["history_complete_7d"] == 1) != (ch["n_obs_prev7"] == 7)).sum())
            for col in RAW_COLUMNS:
                c["diff1_without_both"] += int((ch[col + "_diff1"].notna() & (ch[col].isna() | ch[col + "_prev1"].isna())).sum())
            c["mean7_with_short_history"] += int((ch[RAW_COLUMNS[0] + "_mean7"].notna() & (ch["n_obs_prev7"] < ROLL_WINDOW - 1)).sum())
            for a in PARTIAL_ATTRIBUTES:
                col = f"smart_{a}_raw"
                not_j17 = d != ALTERED_FILE_DATE
                c["missing_flag_vs_value_mismatch"] += int((not_j17 & ((ch[col + "_missing"] == 1) != ch[col].isna())).sum())
            # June 17 safeguards
            j17 = d == ALTERED_FILE_DATE
            c["source_flag_wrong"] += int(((ch["source_file_altered"] == 1) != j17).sum())
            c["june17_rows"] += int(j17.sum())
            for col in MASKED:
                c["june17_masked_non_null"] += int(ch.loc[j17, col].notna().sum())
                c["june18_diff1_non_null_masked"] += int(ch.loc[d == ALTERED_FILE_DATE + pd.Timedelta(days=1), col + "_diff1"].notna().sum())
                win = (d >= ALTERED_FILE_DATE) & (d <= ALTERED_FILE_DATE + pd.Timedelta(days=ROLL_WINDOW - 1))
                c["june17_window_mean7_non_null_masked"] += int(ch.loc[win, col + "_mean7"].notna().sum())
            stats[f"{split}_june17_unmasked_core_non_null"] += int(ch.loc[j17, "smart_9_raw"].notna().sum())
            # keep candidate rows for the independent recomputation
            sample_rows.append(ch.loc[ch["serial_number"].isin(sample), ["serial_number", "date"] + feats])
        counts[split] = dict(c)
        check(f"{split}: dates within approved window", dmin >= lo and dmax <= hi, f"{dmin.date()}..{dmax.date()}")
        if split == "train":
            check("train: no label window crosses into test (max date + 7 < 2019-06-01)",
                  dmax + pd.Timedelta(days=HORIZON_DAYS) < TEST_START, str((dmax + pd.Timedelta(days=HORIZON_DAYS)).date()))
        for k in ("label_primary_invalid", "pos_with_sens_not_1", "fold_mismatch", "rows_on_or_after_failure",
                  "pos_outside_1_7", "neg_with_failure_within_7", "hist_flag_inconsistent", "diff1_without_both",
                  "mean7_with_short_history", "missing_flag_vs_value_mismatch", "source_flag_wrong",
                  "june17_masked_non_null", "june18_diff1_non_null_masked", "june17_window_mean7_non_null_masked"):
            check(f"{split}: {k} == 0", c[k] == 0, str(c[k]))

    check("quality-excluded drives absent from both files", not excl_found, str(sorted(excl_found)))
    check("each serial has exactly one fold across files", fold_conflicts == 0, str(fold_conflicts))
    check("drive-held-out: no drive in both train (fold!=k) and test (fold==k) for any k",
          fold_conflicts == 0 and counts["train"]["fold_mismatch"] == 0 and counts["test"]["fold_mismatch"] == 0,
          "fold is a deterministic function of serial_number")
    check("June 17 rows present in test with core attributes intact",
          counts["test"]["june17_rows"] > 0 and stats["test_june17_unmasked_core_non_null"] > 0,
          f"rows={counts['test']['june17_rows']}, smart_9 non-null={stats['test_june17_unmasked_core_non_null']}")

    # ---------------------------------------------------------------- 3. counts vs methodology
    m = pd.read_csv(METHODOLOGY_COUNTS).set_index("scope")
    mt = m.loc[[i for i in m.index if i.startswith("train examples")][0]]
    ms = m.loc[[i for i in m.index if i.startswith("test examples")][0]]
    comp = []
    for split, ref in (("train", mt), ("test", ms)):
        c = counts[split]
        for name, got, exp in (("positive_rows", c["pos"], ref["positive_rows"]),
                               ("positive_drives", len(pos_drives[split]), ref["positive_drives"]),
                               ("negative_rows_primary", c["neg"], ref["negative_rows_primary"]),
                               ("negative_rows_sensitivity", c["sens_neg"], ref["negative_rows_sensitivity"]),
                               ("unknown_rows_sensitivity_within_primary_rows", c["sens_unknown"],
                                ref["unknown_rows_sensitivity"] - ref["unknown_rows_primary"])):
            comp.append({"split": split, "count": name, "built": int(got), "methodology": int(exp), "match": int(got) == int(exp)})
            check(f"{split}: {name} matches methodology", int(got) == int(exp), f"built={got:,} methodology={int(exp):,}")
    results["count_comparison"] = comp

    # ---------------------------------------------------------------- 4. independent recomputation (no future data)
    built = pd.concat(sample_rows, ignore_index=True).set_index(["serial_number", "date"])
    del sample_rows
    series = defaultdict(dict)                   # serial -> {date: raw values (masked on June 17)}
    for date, path in daily_files():
        df = read_daily(path, ["serial_number"] + RAW_COLUMNS)
        df = df[df["serial_number"].isin(sample)]
        if date == ALTERED_FILE_DATE:
            df.loc[:, MASKED] = np.nan
        for row in df.itertuples(index=False):
            series[row[0]][date] = np.array(row[1:], dtype=float)
    max_err, n_checked, mism = 0.0, 0, 0
    for (s, dstr), brow in built.iterrows():
        t = pd.Timestamp(dstr)
        hist = series[s]                          # only dates <= t are used below
        get = lambda k: hist.get(t - pd.Timedelta(days=k))
        cur, p1, p7 = get(0), get(1), get(7)
        win = [get(k) for k in range(ROLL_WINDOW)]
        nan = np.full(len(RAW_COLUMNS), np.nan)
        exp = {"": cur, "_prev1": p1 if p1 is not None else nan,
               "_diff1": cur - p1 if p1 is not None else nan,
               "_diff7": cur - p7 if p7 is not None else nan}
        if all(w is not None for w in win):
            st = np.stack(win)
            exp["_mean7"], exp["_std7"] = st.mean(axis=0), st.std(axis=0)
        else:
            exp["_mean7"] = exp["_std7"] = nan
        for suf, vals in exp.items():
            got = brow[[c + suf for c in RAW_COLUMNS]].to_numpy(dtype=float)
            both_nan = np.isnan(got) & np.isnan(vals)
            diff = np.where(both_nan, 0, np.abs(got - vals) / np.maximum(1, np.abs(vals)))
            if np.isnan(diff).any():
                mism += 1
            else:
                max_err = max(max_err, float(np.nanmax(diff)))
        n_obs = sum(get(k) is not None for k in range(1, 8))
        if n_obs != brow["n_obs_prev7"]:
            mism += 1
        n_checked += 1
    check("independent past-only recomputation matches written features",
          mism == 0 and max_err < 1e-12, f"{n_checked:,} rows of {len(sample)} drives; NaN-pattern mismatches={mism}; max rel err={max_err:.2e}")

    # ---------------------------------------------------------------- 5. reports
    all_pass = all(v["pass"] for k, v in results.items() if isinstance(v, dict) and "pass" in v)
    results["all_pass"] = all_pass
    results["counts_from_files"] = counts
    results["positive_drives"] = {k: len(v) for k, v in pos_drives.items()}
    with open(PROCESSED_DIR / "validation_results.json", "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    write_feature_manifest(feats, summary)
    write_target_report(summary, counts, pos_drives, comp, all_pass)
    print("ALL PASS" if all_pass else "SOME CHECKS FAILED")


def write_feature_manifest(feats, summary):
    smv = pd.read_csv(PROCESSED_DIR.parent / "results" / "dataset_audit_revalidation" / "smart_missing_values.csv").set_index("column")
    meaning = {1: "Read Error Rate", 3: "Spin-Up Time", 4: "Start/Stop Count", 5: "Reallocated Sectors Count",
               7: "Seek Error Rate", 9: "Power-On Hours", 10: "Spin Retry Count", 12: "Power Cycle Count",
               187: "Reported Uncorrectable Errors", 188: "Command Timeout", 190: "Airflow Temperature",
               192: "Power-off Retract Count", 193: "Load/Unload Cycle Count", 194: "Temperature",
               197: "Current Pending Sector Count", 198: "Offline Uncorrectable Sector Count",
               199: "UltraDMA CRC Error Count", 240: "Head Flying Hours", 241: "Total LBAs Written",
               242: "Total LBAs Read"}
    L = ["# Feature Manifest — 7-day disk-failure dataset", "",
         f"Generated by `validate_dataset.py` from `build_summary.json`. **{len(feats)} model features.**", "",
         "Model input = exactly the columns listed under *Features* below, in this order.",
         "All other columns are metadata or labels and must never be passed to the model.", "",
         "## Metadata (never features)", "",
         "| Column | Purpose |", "|---|---|",
         "| `serial_number` | Grouping / drive-held-out evaluation only |",
         "| `date` | Observation date (file-name date); used for splitting only |",
         "| `model` | Per-model evaluation only |",
         "| `fold` | `crc32(serial_number) % 5`, drive-held-out fold |",
         "| `source_file_altered` | 1 for rows from 2019-06-17.csv; metadata only |", "",
         "## Labels", "",
         "| Column | Values |", "|---|---|",
         "| `label_primary` | 1 = failure in t+1..t+7; 0 = no failure and observed on/after t+7 |",
         "| `label_sensitivity` | 1 / 0 (all 7 future days observed) / empty = sensitivity outcome unknown |", "",
         "## Source attributes", "",
         "Meanings are standard SMART names; raw encodings are vendor-specific.", "",
         "| Attribute | Name | Group | Missing % (all rows) |", "|---|---|---|---|"]
    for a in ATTRIBUTES:
        L.append(f"| `smart_{a}_raw` | {meaning.get(a, '')} | {'core' if a in CORE_ATTRIBUTES else 'partial (+missing flag)'} | "
                 f"{smv.loc[f'smart_{a}_raw', 'missing_pct']:.2f} |")
    L += ["", "## Feature definitions (t = observation day; only days <= t are used)", "",
          "| Pattern | Definition | NaN when |", "|---|---|---|",
          "| `smart_A_raw` | value on t | not reported, or a damaged column on 2019-06-17 |",
          "| `smart_A_raw_prev1` | value on t-1 | t-1 not observed / value missing |",
          "| `smart_A_raw_diff1` | value(t) - value(t-1) | either value unavailable |",
          "| `smart_A_raw_diff7` | value(t) - value(t-7) | either value unavailable |",
          "| `smart_A_raw_mean7` | mean of days t-6..t | any of the 7 days unobserved or missing |",
          "| `smart_A_raw_std7` | population std of days t-6..t | as mean7 |",
          "| `smart_A_raw_missing` | 1 if A not reported on t (A in 187,188,190,240,241,242) | never (0/1); measured before the June-17 masking |",
          "| `n_obs_prev7` | observed days among t-7..t-1 (0-7) | never |",
          "| `history_complete_7d` | 1 if n_obs_prev7 = 7 | never |", "",
          "No zero-filling, no forward-filling across missing dates. The Random Forest (scikit-learn ≥ 1.4) accepts NaN natively.", "",
          "## Feature list (in order)", "", "```"] + feats + ["```", ""]
    (PROCESSED_DIR / "feature_manifest.md").write_text("\n".join(L), encoding="utf-8")


def write_target_report(summary, counts, pos_drives, comp, all_pass):
    j = summary["june17"]
    L = ["# Target Generation Report — 7-day disk failure (Backblaze Q2 2019)", "",
         f"Built by `build_dataset.py` in {summary['runtime_s']:.0f} s; validated by `validate_dataset.py`. "
         f"**Validation: {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED — see validation_results.json'}.**", "",
         "## Label rules (as approved)", "",
         "* Observation date t = file-name date. F = file date of the drive's `failure = 1` record.",
         "* Positive: t < F ≤ t+7. Primary negative: no failure in t+1..t+7 and an observation on/after t+7.",
         "* Sensitivity negative: no failure in t+1..t+7 and observations on all of t+1..t+7.",
         "* Excluded: unknown outcome; failure-day and later records; the 5 quality-excluded drives.", "",
         "## Counts (recounted from the written files) vs methodology", "",
         "| Split | Count | Built | Methodology | Match |", "|---|---|---|---|---|"]
    for r in comp:
        L.append(f"| {r['split']} | {r['count']} | {r['built']:,} | {r['methodology']:,} | {'yes' if r['match'] else '**NO**'} |")
    L += ["", "## Written examples", "",
          "| File | Rows | Positives (drives) | Primary negatives | Sensitivity-eligible rows |", "|---|---|---|---|---|"]
    for s in ("train", "test"):
        c = counts[s]
        L.append(f"| `{s}_chronological.csv.gz` | {c['rows']:,} | {c['pos']:,} ({len(pos_drives[s])}) | {c['neg']:,} | {c['sens_pos'] + c['sens_neg']:,} |")
    L += ["", "## 2019-06-17 safeguard", "",
          f"* Rows from the altered file written to the test set: {j.get('rows_written', 0):,} ({j.get('positive_rows', 0)} positives); `source_file_altered = 1`.",
          f"* Set to NaN on that day: {', '.join(j.get('masked_columns', []))} (non-null before masking: {j.get('non_null_before_mask', {})}).",
          f"* {', '.join(j.get('not_read_damaged_columns', []))} are damaged too but are not used by the pipeline.",
          "* Derived features whose window includes 2019-06-17 are NaN for these columns (diff1 on 06-18, mean7/std7 on 06-17..06-23).", "",
          "## Validation assertions", ""]
    for k, v in results.items():
        if isinstance(v, dict) and "pass" in v:
            L.append(f"* {'PASS' if v['pass'] else '**FAIL**'} — {k} {('(' + v['detail'] + ')') if v['detail'] else ''}")
    (PROCESSED_DIR / "target_generation_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
