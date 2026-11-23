#!/usr/bin/env python
"""
Backblaze Q2 2019 dataset audit (read-only).

Project: Predictive Disk Failure-Aware Adaptive Checkpointing for Fault-Tolerant
Cloud Task Scheduling.

The script streams every daily CSV in fixed-size chunks (pandas `chunksize`) and
aggregates incrementally. It never concatenates the raw daily files. The only
dataset-wide structure it keeps is a compact integer index of
(drive_id, day, model_id, failure), about 10 bytes per row, which is needed for
drive-level chronological analysis: observations before failure, censoring, and
7-day label feasibility counts.

It does NOT train a model, write a training set, or modify any CSV.

Usage (from the project root C:/Users/rushi/CC_project):
    python -I project/ml/preprocessing/inspect_dataset.py
    python -I project/ml/preprocessing/inspect_dataset.py --data project/dataset/backblaze_q2_2019 \
        --out project/ml/results/dataset_audit --chunksize 50000
"""
import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

ID_COLS = ["date", "serial_number", "model", "capacity_bytes", "failure"]
FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%y"]     # ISO (original) and US short (spreadsheet re-save)
HORIZON_DAYS = 7                             # feasibility counts only
SPLIT_CUTOFF = "2019-06-01"                  # illustrative chronological split (counts only)
EPOCH = pd.Timestamp("2019-01-01")


# --------------------------------------------------------------------------- #
# File-level helpers
# --------------------------------------------------------------------------- #
def list_daily_files(data_dir):
    files = sorted(f for f in os.listdir(data_dir) if FILE_RE.match(f))
    others = sorted(f for f in os.listdir(data_dir) if not FILE_RE.match(f))
    if not files:
        sys.exit(f"No YYYY-MM-DD.csv files found in {data_dir}")
    return [os.path.join(data_dir, f) for f in files], others


def sniff_file(path):
    """Detect line terminator and count scientific-notation tokens (precision-loss marker)."""
    with open(path, "rb") as fh:
        head = fh.read(1 << 16)
    if b"\r\n" in head:
        term, term_name = None, "CRLF"
    elif b"\n" in head:
        term, term_name = None, "LF"
    elif b"\r" in head:
        term, term_name = "\r", "CR-only"
    else:
        term, term_name = None, "unknown"
    sci = 0
    pat = re.compile(rb"\d\.?\d*E\+\d+")
    with open(path, "rb") as fh:
        while True:
            block = fh.read(1 << 24)
            if not block:
                break
            if b"E+" in block:
                sci += len(pat.findall(block))
    header = head.replace(b"\r", b"\n").split(b"\n", 1)[0].decode("utf-8", "replace").split(",")
    return term, term_name, sci, header


def parse_dates(s):
    """Parse a date column trying each known format; return (Timestamps, format_counts)."""
    out = pd.Series(pd.NaT, index=s.index)
    used = Counter()
    rest = s.notna()
    for fmt in DATE_FORMATS:
        p = pd.to_datetime(s[rest], format=fmt, errors="coerce")
        ok = p.notna()
        out.loc[p.index[ok]] = p[ok]
        used[fmt] += int(ok.sum())
        rest = rest & out.isna()
    return out, used


# --------------------------------------------------------------------------- #
# Incremental accumulators
# --------------------------------------------------------------------------- #
class ColumnStats:
    """Non-null counts, min/max, negative and out-of-range counts per numeric column."""

    def __init__(self):
        self.rows = 0
        self.non_null = Counter()
        self.non_null_fail = Counter()
        self.rows_fail = 0
        self.mins, self.maxs = {}, {}
        self.negative = Counter()
        self.norm_out_of_range = Counter()
        self.coerce_fail = Counter()

    def update(self, num, failure_mask):
        self.rows += len(num)
        self.rows_fail += int(failure_mask.sum())
        nn = num.notna().sum()
        nnf = num[failure_mask].notna().sum()
        mn, mx = num.min(), num.max()
        neg = (num < 0).sum()
        for c in num.columns:
            self.non_null[c] += int(nn[c])
            self.non_null_fail[c] += int(nnf[c])
            self.negative[c] += int(neg[c])
            if pd.notna(mn[c]):
                self.mins[c] = min(self.mins.get(c, np.inf), float(mn[c]))
                self.maxs[c] = max(self.maxs.get(c, -np.inf), float(mx[c]))
            if c.endswith("_normalized"):
                self.norm_out_of_range[c] += int(((num[c] < 0) | (num[c] > 255)).sum())


class DriveIndex:
    """Compact (drive_id, day, model_id, failure) index + string<->id maps."""

    def __init__(self):
        self.serial_id, self.model_id = {}, {}
        self.parts = []

    def _ids(self, values, mapping):
        s = pd.Series(values)
        ids = s.map(mapping)
        for v in s[ids.isna()].unique():
            mapping[v] = len(mapping)
        return s.map(mapping).to_numpy()

    def add(self, serials, models, day, failure):
        sid = self._ids(serials, self.serial_id).astype(np.int32)
        mid = self._ids(models, self.model_id).astype(np.int16)
        self.parts.append(pd.DataFrame({"sid": sid, "day": np.int16(day), "mid": mid,
                                        "failure": failure.astype(np.int8)}))

    def frame(self):
        k = pd.concat(self.parts, ignore_index=True)
        self.parts = []
        return k.sort_values(["sid", "day"], kind="mergesort").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Main streaming pass
# --------------------------------------------------------------------------- #
def audit(files, chunksize):
    cols_ref = None
    smart_cols = None
    cs = ColumnStats()
    idx = DriveIndex()
    per_file = []
    invalid = Counter()
    date_formats = Counter()
    model_caps = defaultdict(Counter)
    date_mismatch_examples = []

    for i, path in enumerate(files):
        fname = os.path.basename(path)
        file_day_ts = pd.Timestamp(FILE_RE.match(fname).group(1))
        file_day = int((file_day_ts - EPOCH).days)
        term, term_name, sci, header = sniff_file(path)
        if cols_ref is None:
            cols_ref = header
            smart_cols = [c for c in header if c.startswith("smart_")]
        rec = {"file": fname, "size_bytes": os.path.getsize(path), "line_terminator": term_name,
               "header_matches_first_file": header == cols_ref, "sci_notation_cells": sci,
               "rows": 0, "failures": 0, "dup_serial_rows": 0, "dup_full_rows": 0,
               "date_mismatch_rows": 0, "unparseable_dates": 0, "nonstandard_date_format_rows": 0}
        seen_serials = set()
        seen_hashes = set()
        reader = pd.read_csv(path, chunksize=chunksize, lineterminator=term, low_memory=False,
                             dtype={"date": str, "serial_number": str, "model": str})
        for ch in reader:
            n = len(ch)
            rec["rows"] += n
            # ---- dates ----
            dts, used = parse_dates(ch["date"])
            date_formats.update(used)
            rec["nonstandard_date_format_rows"] += sum(v for k, v in used.items() if k != "%Y-%m-%d")
            rec["unparseable_dates"] += int(dts.isna().sum())
            mism = dts.notna() & (dts != file_day_ts)
            rec["date_mismatch_rows"] += int(mism.sum())
            for _, r in ch.loc[mism, ["date", "serial_number", "failure"]].head(5).iterrows():
                date_mismatch_examples.append((fname, r["date"], r["serial_number"], r["failure"]))
            # ---- numeric coercion ----
            num_cols = ["capacity_bytes", "failure"] + smart_cols
            before = ch[num_cols].notna().sum()
            num = ch[num_cols].apply(pd.to_numeric, errors="coerce")
            lost = before - num.notna().sum()
            for c in lost.index[lost > 0]:
                cs.coerce_fail[c] += int(lost[c])
            fail = num["failure"]
            # ---- invalid values ----
            invalid["failure_not_0_or_1"] += int((~fail.isin([0, 1])).sum())
            invalid["capacity_bytes_missing"] += int(num["capacity_bytes"].isna().sum())
            invalid["capacity_bytes_nonpositive"] += int((num["capacity_bytes"] <= 0).sum())
            invalid["serial_missing"] += int(ch["serial_number"].isna().sum())
            invalid["model_missing"] += int(ch["model"].isna().sum())
            fmask = (fail == 1).to_numpy()
            rec["failures"] += int(fmask.sum())
            cs.update(num[smart_cols], fmask)
            # model -> capacity consistency (vectorised)
            mc =pd.DataFrame({"m": ch["model"], "c": num["capacity_bytes"]}).value_counts()
            for (m, c), k in mc.items():
                model_caps[m][c] += int(k)
            # ---- duplicates (within the daily file) ----
            ser = ch["serial_number"]
            dup_in_chunk = ser.duplicated()
            dup_prev = ser.isin(seen_serials)
            rec["dup_serial_rows"] += int((dup_in_chunk | dup_prev).sum())
            seen_serials.update(ser.dropna())
            h = pd.util.hash_pandas_object(ch, index=False)
            rec["dup_full_rows"] += int((h.duplicated() | h.isin(seen_hashes)).sum())
            seen_hashes.update(h)
            # ---- compact index (observation day = file date) ----
            ok = ser.notna().to_numpy()
            idx.add(ser[ok].to_numpy(), ch["model"].fillna("<missing>")[ok].to_numpy(), file_day,
                    fail.fillna(-1).to_numpy()[ok])
        rec["unique_serials"] = len(seen_serials)
        per_file.append(rec)
        print(f"  [{i + 1:>2}/{len(files)}] {fname}  rows={rec['rows']:,}  failures={rec['failures']}"
              f"  terminator={term_name}  sci={sci}", flush=True)
    return dict(cols=cols_ref, smart_cols=smart_cols, cs=cs, key=idx.frame(), idx=idx,
                per_file=pd.DataFrame(per_file), invalid=invalid, date_formats=date_formats,
                model_caps=model_caps, date_mismatch_examples=date_mismatch_examples)


# --------------------------------------------------------------------------- #
# Drive-level chronological analysis
# --------------------------------------------------------------------------- #
def drive_analysis(key, start_day, end_day):
    g = key.groupby("sid")
    drv = pd.DataFrame({"first_day": g["day"].min(), "last_day": g["day"].max(), "n_obs": g.size(),
                        "n_models": g["mid"].nunique(), "mid": g["mid"].first()})
    drv["n_failure_records"] = (key["failure"] == 1).groupby(key["sid"]).sum()
    drv["fail_day"] = key[key["failure"] == 1].groupby("sid")["day"].min()
    drv["span"] = drv["last_day"] - drv["first_day"] + 1
    drv["missing_days_in_span"] = drv["span"] - drv["n_obs"]
    failed = drv[drv["fail_day"].notna()].copy()
    k2 = key.merge(failed[["fail_day"]], left_on="sid", right_index=True)
    before = k2["day"] < k2["fail_day"]
    failed["obs_before_failure"] = k2[before].groupby("sid").size()
    failed["obs_in_7d_before_failure"] = k2[before & (k2["day"] >= k2["fail_day"] - 7)].groupby("sid").size()
    failed["rows_after_failure"] = k2[k2["day"] > k2["fail_day"]].groupby("sid").size()
    failed["prev_obs_day"] = k2[before].groupby("sid")["day"].max()
    failed = failed.fillna({"obs_before_failure": 0, "obs_in_7d_before_failure": 0, "rows_after_failure": 0})
    failed["gap_days_prev_obs_to_failure"] = failed["fail_day"] - failed["prev_obs_day"]
    failed["failure_is_last_observation"] = failed["last_day"] == failed["fail_day"]
    failed["first_seen_on_first_day"] = failed["first_day"] == start_day
    return drv, failed


def horizon_feasibility(key, drv, H, start_day, end_day, cutoff_day):
    """Counts only. Positive: failure in (t, t+H]. Negative: drive known alive at t+H.
    Excluded: failure-day rows, rows after failure, censored rows (follow-up < H days)."""
    f = key["sid"].map(drv["fail_day"]).to_numpy()
    L = key["sid"].map(drv["last_day"]).to_numpy()
    t = key["day"].to_numpy().astype(np.int32)
    sid = key["sid"].to_numpy()
    failed = ~np.isnan(f)
    fz = np.where(failed, f, 1e9)
    pos = failed & (t < fz) & (fz - t <= H)
    neg = (failed & (t < fz) & (fz - t > H)) | (~failed & (L >= t + H))
    fail_row = failed & (t == fz)
    after = failed & (t > fz)
    cens = ~failed & (L < t + H)
    cens_end = cens & (L == end_day)
    out = {
        "positive_rows": int(pos.sum()), "positive_drives": int(np.unique(sid[pos]).size),
        "negative_rows": int(neg.sum()), "negative_drives": int(np.unique(sid[neg]).size),
        "excluded_failure_day_rows": int(fail_row.sum()), "excluded_rows_after_failure": int(after.sum()),
        "censored_rows_end_of_dataset": int(cens_end.sum()),
        "censored_rows_drive_left_without_failure": int((cens & ~cens_end).sum()),
        "neg_per_pos": round(neg.sum() / max(pos.sum(), 1), 1),
    }
    train = t + H < cutoff_day
    test = t >= cutoff_day
    out["train_positive_rows"] = int((pos & train).sum())
    out["train_positive_drives"] = int(np.unique(sid[pos & train]).size)
    out["train_negative_rows"] = int((neg & train).sum())
    out["test_positive_rows"] = int((pos & test).sum())
    out["test_positive_drives"] = int(np.unique(sid[pos & test]).size)
    out["test_negative_rows"] = int((neg & test).sum())
    out["purged_boundary_rows"] = int(((t < cutoff_day) & ~train & (pos | neg)).sum())
    return out


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join("project", "dataset", "backblaze_q2_2019"))
    ap.add_argument("--out", default=os.path.join("project", "ml", "results", "dataset_audit"))
    ap.add_argument("--chunksize", type=int, default=50_000)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    files, other_files = list_daily_files(a.data)
    print(f"Auditing {len(files)} daily files in {a.data} (chunksize={a.chunksize:,})")
    R = audit(files, a.chunksize)
    key, cs, pf = R["key"], R["cs"], R["per_file"]
    inv_serial = np.empty(len(R["idx"].serial_id), dtype=object)
    for s, i in R["idx"].serial_id.items():
        inv_serial[i] = s
    inv_model = {i: m for m, i in R["idx"].model_id.items()}
    start_day, end_day = int(key["day"].min()), int(key["day"].max())
    day_to_date = lambda d: (EPOCH + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d")

    drv, failed = drive_analysis(key, start_day, end_day)
    dup_serial_day = int(key.duplicated(["sid", "day"]).sum())

    # ---------------- daily_failure_counts.csv ----------------
    daily = pf[["file", "rows", "unique_serials", "failures"]].copy()
    daily.insert(0, "date", daily["file"].str[:10])
    daily["failure_rate_per_100k_drive_days"] = (daily["failures"] / daily["rows"] * 1e5).round(3)
    daily.drop(columns="file").to_csv(os.path.join(a.out, "daily_failure_counts.csv"), index=False)

    # ---------------- drive_failure_summary.csv ----------------
    failed["serial_number"] = inv_serial[failed.index.to_numpy()]
    failed["model"] = failed["mid"].map(inv_model)
    for c in ("first_day", "last_day", "fail_day"):
        failed[c.replace("_day", "_date") if c != "fail_day" else "failure_date"] = failed[c].map(day_to_date)
    failed["flag_failure_after_gap"] = failed["gap_days_prev_obs_to_failure"] > 1
    failed["flag_rows_after_failure"] = failed["rows_after_failure"] > 0
    failed["flag_no_prior_observation"] = failed["obs_before_failure"] == 0
    failed["flag_multiple_failure_records"] = failed["n_failure_records"] > 1
    fcols = ["serial_number", "model", "first_date", "failure_date", "last_date", "first_seen_on_first_day",
             "n_obs", "obs_before_failure", "obs_in_7d_before_failure", "gap_days_prev_obs_to_failure",
             "n_failure_records", "rows_after_failure", "failure_is_last_observation",
             "flag_failure_after_gap", "flag_rows_after_failure", "flag_no_prior_observation",
             "flag_multiple_failure_records"]
    failed[fcols].sort_values("failure_date").to_csv(os.path.join(a.out, "drive_failure_summary.csv"), index=False)

    # ---------------- smart_missing_values.csv ----------------
    rows = []
    for c in R["smart_cols"]:
        m = re.match(r"smart_(\d+)_(raw|normalized)", c)
        nn = cs.non_null[c]
        rows.append({"column": c, "attribute_id": int(m.group(1)), "value_type": m.group(2),
                     "non_null": nn, "missing": cs.rows - nn,
                     "missing_pct": round(100 * (cs.rows - nn) / cs.rows, 4),
                     "missing_pct_in_failure_records": round(100 * (cs.rows_fail - cs.non_null_fail[c]) / max(cs.rows_fail, 1), 2),
                     "min": cs.mins.get(c), "max": cs.maxs.get(c),
                     "negative_values": cs.negative[c],
                     "normalized_out_of_0_255": cs.norm_out_of_range[c] if c.endswith("_normalized") else None,
                     "non_numeric_values": cs.coerce_fail[c]})
    sm = pd.DataFrame(rows).sort_values(["missing_pct", "attribute_id", "value_type"])
    sm.to_csv(os.path.join(a.out, "smart_missing_values.csv"), index=False)

    # ---------------- model_failure_summary.csv ----------------
    bm = key.groupby("mid").agg(drive_days=("sid", "size"))
    bm["drives"] = drv.groupby("mid").size()
    bm["failed_drives"] = failed.groupby("mid").size()
    bm["failure_records"] = key[key["failure"] == 1].groupby("mid").size()
    bm = bm.fillna(0).astype(int)
    bm["annualized_failure_rate_pct"] = (bm["failed_drives"] / (bm["drive_days"] / 365) * 100).round(3)
    bm.insert(0, "model", bm.index.map(inv_model))
    caps = {m: "|".join(str(int(c)) if pd.notna(c) else "NaN" for c in R["model_caps"][m]) for m in R["model_caps"]}
    bm["capacity_bytes_values"] = bm["model"].map(caps)
    bm = bm.sort_values("drive_days", ascending=False)
    bm.to_csv(os.path.join(a.out, "model_failure_summary.csv"), index=False)

    # ---------------- feasibility counts ----------------
    cutoff_day = int((pd.Timestamp(SPLIT_CUTOFF) - EPOCH).days)
    flagged = failed.index[failed["flag_failure_after_gap"] | failed["flag_rows_after_failure"]
                           | failed["flag_multiple_failure_records"]]
    feas = {}
    for H in (1, 3, HORIZON_DAYS):
        feas[H] = horizon_feasibility(key, drv, H, start_day, end_day, cutoff_day)
    feas_clean = horizon_feasibility(key[~key["sid"].isin(flagged)], drv, HORIZON_DAYS, start_day, end_day, cutoff_day)
    ob = failed["obs_before_failure"]
    coverage_raw = sm[sm["value_type"] == "raw"].set_index("attribute_id")["missing_pct"]
    good = coverage_raw[coverage_raw <= 5].index.tolist()
    mid_ = coverage_raw[(coverage_raw > 5) & (coverage_raw <= 50)].index.tolist()
    poor = coverage_raw[(coverage_raw > 50) & (coverage_raw < 100)].index.tolist()
    empty = coverage_raw[coverage_raw >= 100].index.tolist()

    # ---------------- dataset_summary.txt ----------------
    total_rows = int(len(key))
    n_fail_rows = int((key["failure"] == 1).sum())
    L = []
    w = L.append
    w("BACKBLAZE Q2 2019 DATASET AUDIT")
    w("=" * 72)
    w(f"Generated by project/ml/preprocessing/inspect_dataset.py in {time.time() - t0:.0f} s; chunksize={a.chunksize:,}")
    w(f"Data directory: {os.path.abspath(a.data)}")
    w(f"Daily CSV files: {len(files)}   other files in directory: {other_files or 'none'}")
    w(f"Total size: {pf['size_bytes'].sum() / 2**30:.2f} GiB")
    w("")
    w("1. CORE COUNTS (confirmed)")
    w(f"  Earliest date (file)            : {day_to_date(start_day)}")
    w(f"  Latest date (file)              : {day_to_date(end_day)}")
    w(f"  Calendar days / files present   : {end_day - start_day + 1} / {len(files)}")
    w(f"  Total records (drive-days)      : {total_rows:,}")
    w(f"  Unique drive serial numbers     : {len(drv):,}")
    w(f"  Records with failure = 1        : {n_fail_rows:,}")
    w(f"  Records with failure = 0        : {int((key['failure'] == 0).sum()):,}")
    w(f"  Unique failed drives            : {len(failed):,}")
    w(f"  Drives with no failure record   : {len(drv) - len(failed):,}  (NOT guaranteed healthy beyond their observed period)")
    w(f"    - of which still present on last day : {int(((drv['fail_day'].isna()) & (drv['last_day'] == end_day)).sum()):,}")
    w(f"    - of which left before last day w/o failure (censored): {int(((drv['fail_day'].isna()) & (drv['last_day'] < end_day)).sum()):,}")
    w(f"  Drive models                    : {len(inv_model)}")
    w(f"  Row-level failure rate          : {100 * n_fail_rows / total_rows:.4f} %  (1 : {total_rows / max(n_fail_rows, 1):,.0f})")
    w(f"  Annualised failure rate (all)   : {len(failed) / (total_rows / 365) * 100:.2f} %")
    w(f"  Daily drive count min/median/max: {daily['rows'].min():,} / {int(daily['rows'].median()):,} / {daily['rows'].max():,}")
    w(f"  Daily failures min/median/max   : {daily['failures'].min()} / {daily['failures'].median():.0f} / {daily['failures'].max()}")
    w("")
    w("2. SCHEMA / SMART ATTRIBUTES (confirmed)")
    w(f"  Columns: {len(R['cols'])}  (5 identifier columns + {len(R['smart_cols'])} SMART columns)")
    n_attr = len({c.split("_")[1] for c in R["smart_cols"]})
    w(f"  SMART attributes: {n_attr} attribute IDs, each with _normalized and _raw")
    w(f"  Header identical in all files   : {bool(pf['header_matches_first_file'].all())}")
    w(f"  Raw attributes <=5 % missing    : {good}")
    w(f"  Raw attributes 5-50 % missing   : {mid_}")
    w(f"  Raw attributes 50-<100 % missing: {poor}")
    w(f"  Raw attributes 100 % missing    : {empty}")
    w("  (full table: smart_missing_values.csv)")
    w("")
    w("3. DUPLICATES AND INVALID VALUES (confirmed)")
    w(f"  Duplicate (serial, day) records : {dup_serial_day:,}")
    w(f"  Duplicate full rows within files: {int(pf['dup_full_rows'].sum()):,}")
    for k_, v in R["invalid"].items():
        w(f"  {k_:<32}: {v:,}")
    w(f"  Negative SMART values (all cols): {sum(cs.negative.values()):,}")
    w(f"  Normalized values outside 0-255 : {sum(cs.norm_out_of_range.values()):,}")
    w(f"  Non-numeric SMART values        : {sum(cs.coerce_fail.values()):,}")
    w(f"  Serials with >1 model           : {int((drv['n_models'] > 1).sum()):,}")
    multi_cap = [m for m, c in R["model_caps"].items() if len(c) > 1]
    w(f"  Models with >1 capacity value   : {len(multi_cap)} {multi_cap[:10]}")
    w("")
    w("4. FILE INTEGRITY (confirmed)")
    bad = pf[(pf["line_terminator"] != pf["line_terminator"].mode()[0]) | (pf["sci_notation_cells"] > 0)
             | (pf["date_mismatch_rows"] > 0) | (pf["nonstandard_date_format_rows"] > 0) | (~pf["header_matches_first_file"])]
    w(f"  Normal line terminator          : {pf['line_terminator'].mode()[0]}")
    if bad.empty:
        w("  No anomalous files detected.")
    for _, r in bad.iterrows():
        w(f"  ANOMALOUS FILE {r['file']}: terminator={r['line_terminator']}, rows={r['rows']:,}, "
          f"non-ISO date rows={r['nonstandard_date_format_rows']:,}, date!=filename rows={r['date_mismatch_rows']}, "
          f"scientific-notation cells={r['sci_notation_cells']:,}")
    for ex in R["date_mismatch_examples"][:10]:
        w(f"    date mismatch example: file={ex[0]} date={ex[1]} serial={ex[2]} failure={ex[3]}")
    w("  Note: observation day is taken from the FILE NAME; row-level date mismatches are reported, not corrected.")
    w("")
    w("5. FAILED-DRIVE CHRONOLOGY (confirmed)")
    w(f"  Failure record is the drive's last observation : {int(failed['failure_is_last_observation'].sum())} / {len(failed)}")
    w(f"  Drives with rows after their failure record     : {int(failed['flag_rows_after_failure'].sum())}")
    w(f"  Drives with >1 failure record                   : {int(failed['flag_multiple_failure_records'].sum())}")
    w(f"  Failure recorded after an observation gap >1 day: {int(failed['flag_failure_after_gap'].sum())}")
    w(f"  Failed drives present on first day              : {int(failed['first_seen_on_first_day'].sum())}")
    w(f"  Observations before failure: min {int(ob.min())}, P25 {ob.quantile(.25):.0f}, median {ob.median():.0f}, "
      f"mean {ob.mean():.1f}, P75 {ob.quantile(.75):.0f}, max {int(ob.max())}")
    for k_ in (0, 1, 7, 14, 30, 60):
        w(f"    failed drives with >= {k_:>2} prior observations : {int((ob >= k_).sum())}" if k_ else
          f"    failed drives with 0 prior observations   : {int((ob == 0).sum())}")
    w(f"    failed drives with all 7 days before failure observed: {int((failed['obs_in_7d_before_failure'] == 7).sum())}")
    w("")
    w("6. FUTURE-FAILURE LABEL FEASIBILITY (counts only; no labels written)")
    w("  Positive: failure record in (t, t+H]; Negative: drive observed alive at/after t+H;")
    w("  Excluded: failure-day rows, rows after failure, censored rows (follow-up < H days).")
    for H, f_ in feas.items():
        w(f"  H={H}d : pos rows {f_['positive_rows']:,} ({f_['positive_drives']} drives) | neg rows {f_['negative_rows']:,} | "
          f"neg:pos {f_['neg_per_pos']:,}:1 | censored end {f_['censored_rows_end_of_dataset']:,} | "
          f"censored left {f_['censored_rows_drive_left_without_failure']:,} | failure-day rows {f_['excluded_failure_day_rows']}")
    fc = feas_clean
    w(f"  H={HORIZON_DAYS}d excluding {len(flagged)} flagged failed drives: pos rows {fc['positive_rows']:,} "
      f"({fc['positive_drives']} drives), neg rows {fc['negative_rows']:,}")
    f7 = feas[HORIZON_DAYS]
    w(f"  Chronological split preview (H={HORIZON_DAYS}d, cutoff {SPLIT_CUTOFF}, purge {HORIZON_DAYS}d):")
    w(f"    train ({day_to_date(start_day)}..{day_to_date(cutoff_day - 1 - HORIZON_DAYS)}): "
      f"pos {f7['train_positive_rows']:,} rows / {f7['train_positive_drives']} drives, neg {f7['train_negative_rows']:,}")
    w(f"    test  ({SPLIT_CUTOFF}..{day_to_date(end_day - HORIZON_DAYS)}): "
      f"pos {f7['test_positive_rows']:,} rows / {f7['test_positive_drives']} drives, neg {f7['test_negative_rows']:,}")
    w(f"    rows purged at boundary: {f7['purged_boundary_rows']:,}")
    w("")
    w("7. TOP MODELS BY FAILED DRIVES (full table: model_failure_summary.csv)")
    for _, r in bm.sort_values("failed_drives", ascending=False).head(10).iterrows():
        w(f"  {r['model']:<26} drives {r['drives']:>7,}  failed {r['failed_drives']:>4}  AFR {r['annualized_failure_rate_pct']:.2f} %")
    w("")
    w("OUTPUT FILES: dataset_summary.txt, daily_failure_counts.csv, drive_failure_summary.csv,")
    w("              smart_missing_values.csv, model_failure_summary.csv, file_integrity.csv")
    pf.to_csv(os.path.join(a.out, "file_integrity.csv"), index=False)
    with open(os.path.join(a.out, "dataset_summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
