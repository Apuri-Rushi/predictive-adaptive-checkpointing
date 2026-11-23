#!/usr/bin/env python
"""
COUNTS ONLY: how many examples the approved 7-day target and splits would yield.
No label file, training set or model is produced.

Reads only date/serial_number/model/failure from each daily file (chunked).
The observation day is taken from the file name (see the audit for why).

Label rules for a drive observation on day t (F = day of the drive's failure record):
  excluded_failure_or_after : t >= F                 (failure-day and post-failure records)
  positive                  : t < F <= t+7
  primary negative          : no failure in (t, t+7] and the drive has an observation on/after t+7
  sensitivity negative      : no failure in (t, t+7] and observations exist on all 7 days t+1..t+7
  unknown                   : anything else (excluded)
Drives with unreliable failure records (see QUALITY_EXCLUDED_REASONS) are excluded entirely.

Usage (from C:/Users/rushi/CC_project):
    python -I project/ml/preprocessing/target_feasibility_counts.py
"""
import argparse
import os
import re
import zlib

import numpy as np
import pandas as pd

H = 7
EPOCH = pd.Timestamp("2019-01-01")
TRAIN = ("2019-04-01", "2019-05-24")
PURGE = ("2019-05-25", "2019-05-31")
TEST = ("2019-06-01", "2019-06-23")
N_FOLDS = 5
FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")


def day(s):
    return int((pd.Timestamp(s) - EPOCH).days)


def load_index(data_dir, chunksize):
    parts, sid_map, serials = [], {}, []
    for f in sorted(x for x in os.listdir(data_dir) if FILE_RE.match(x)):
        p = os.path.join(data_dir, f)
        with open(p, "rb") as fh:
            head = fh.read(1 << 16)
        lt = "\r" if (b"\r" in head and b"\n" not in head) else None
        d = day(f[:10])
        for ch in pd.read_csv(p, usecols=["serial_number", "model", "failure"], chunksize=chunksize,
                              lineterminator=lt, dtype={"serial_number": str, "model": str}):
            s = ch["serial_number"]
            ids = s.map(sid_map)
            for v in s[ids.isna()].unique():
                sid_map[v] = len(serials)
                serials.append(v)
            parts.append(pd.DataFrame({"sid": s.map(sid_map).astype(np.int32), "day": np.int16(d),
                                       "model": ch["model"].astype("category"),
                                       "failure": ch["failure"].astype(np.int8)}))
    k = pd.concat(parts, ignore_index=True)
    k["model"] = k["model"].astype(str).astype("category")
    return k.sort_values(["sid", "day"], kind="mergesort").reset_index(drop=True), np.array(serials, dtype=object)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="project/dataset/backblaze_q2_2019")
    ap.add_argument("--audit", default="project/ml/results/dataset_audit_revalidation/drive_failure_summary.csv")
    ap.add_argument("--out", default="project/ml/results/dataset_audit_revalidation")
    ap.add_argument("--chunksize", type=int, default=200_000)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    key, serials = load_index(a.data, a.chunksize)
    sid = key["sid"].to_numpy()
    t = key["day"].to_numpy().astype(np.int64)
    end_day = int(t.max())

    # ---- quality exclusions (drive level), taken from the audit output ----
    fds = pd.read_csv(a.audit)
    reasons = {}
    for _, r in fds.iterrows():
        why = []
        if r["flag_rows_after_failure"]:
            why.append("records after failure record")
        if r["flag_failure_after_gap"]:
            why.append(f"failure recorded after {int(r['gap_days_prev_obs_to_failure'])}-day observation gap")
        if r["flag_multiple_failure_records"]:
            why.append("multiple failure records")
        if why:
            reasons[r["serial_number"]] = "; ".join(why)
    # Failure row in 2019-06-17.csv whose own date column says 6/15/19 (spreadsheet-altered file).
    reasons.setdefault("ZCH0CJC3", "failure row dated 6/15/19 inside 2019-06-17.csv (date conflict)")
    excl_sids = {i for i, s in enumerate(serials) if s in reasons}

    # ---- per-drive failure day / last day ----
    fail_day = key.loc[key["failure"] == 1].groupby("sid")["day"].min()
    last_day = key.groupby("sid")["day"].max()
    F = pd.Series(sid).map(fail_day).to_numpy()
    L = pd.Series(sid).map(last_day).to_numpy()
    failed = ~np.isnan(F)
    Fz = np.where(failed, F, 1e9)

    # ---- observations inside (t, t+7] and [t-7, t-1] for the same drive ----
    comb = sid.astype(np.int64) * 10_000 + t
    pos_idx = np.arange(len(comb))
    n_future = np.searchsorted(comb, comb + H, side="right") - (pos_idx + 1)
    n_past7 = pos_idx - np.searchsorted(comb, comb - H, side="left")

    quality = np.isin(sid, list(excl_sids))
    after = failed & (t >= Fz)
    pos = ~quality & ~after & failed & (Fz - t <= H)
    no_fail_in_window = ~quality & ~after & ~pos
    neg_primary = no_fail_in_window & (L >= t + H)
    neg_sens = no_fail_in_window & (n_future == H)
    unknown_primary = no_fail_in_window & ~neg_primary
    unknown_sens = no_fail_in_window & ~neg_sens
    full_hist = n_past7 == H

    tr = (t >= day(TRAIN[0])) & (t <= day(TRAIN[1]))
    pg = (t >= day(PURGE[0])) & (t <= day(PURGE[1]))
    te = (t >= day(TEST[0])) & (t <= day(TEST[1]))
    tail = t > day(TEST[1])
    # sanity: no training label window crosses into the test period
    assert (t[tr] + H < day(TEST[0])).all()

    rows = []

    def add(scope, m):
        rows.append({
            "scope": scope, "observation_rows": int(m.sum()),
            "excluded_quality_drives": int((m & quality).sum()),
            "excluded_failure_day_or_after": int((m & after & ~quality).sum()),
            "positive_rows": int((m & pos).sum()), "positive_drives": int(np.unique(sid[m & pos]).size),
            "negative_rows_primary": int((m & neg_primary).sum()),
            "unknown_rows_primary": int((m & unknown_primary).sum()),
            "neg_per_pos_primary": round((m & neg_primary).sum() / max((m & pos).sum(), 1), 1),
            "negative_rows_sensitivity": int((m & neg_sens).sum()),
            "unknown_rows_sensitivity": int((m & unknown_sens).sum()),
            "neg_per_pos_sensitivity": round((m & neg_sens).sum() / max((m & pos).sum(), 1), 1),
            "eligible_rows_with_full_7day_history_pct": round(
                100 * (m & (pos | neg_primary) & full_hist).sum() / max((m & (pos | neg_primary)).sum(), 1), 2),
            "positive_rows_with_full_7day_history": int((m & pos & full_hist).sum()),
        })

    all_ = np.ones(len(t), bool)
    add("all observations", all_)
    add(f"train examples {TRAIN[0]}..{TRAIN[1]}", tr)
    add(f"purged rows {PURGE[0]}..{PURGE[1]} (not examples)", pg)
    add(f"test examples {TEST[0]}..{TEST[1]}", te)
    add("censored tail 2019-06-24..2019-06-30 (not examples)", tail)
    add("observations dated 2019-06-17 (altered file)", t == day("2019-06-17"))
    counts = pd.DataFrame(rows)
    counts.to_csv(os.path.join(a.out, "target_label_counts.csv"), index=False)

    # ---- drive-held-out (secondary) evaluation: deterministic hash folds ----
    fold_of_sid = np.array([zlib.crc32(str(s).encode()) % N_FOLDS for s in serials])
    fold = fold_of_sid[sid]
    fr = []
    for k in range(N_FOLDS):
        trm = tr & (fold != k)
        tem = te & (fold == k)
        overlap = np.intersect1d(np.unique(sid[trm & (pos | neg_primary)]), np.unique(sid[tem & (pos | neg_primary)])).size
        fr.append({"fold": k,
                   "train_rows_pos": int((trm & pos).sum()), "train_drives_pos": int(np.unique(sid[trm & pos]).size),
                   "train_rows_neg_primary": int((trm & neg_primary).sum()),
                   "test_rows_pos": int((tem & pos).sum()), "test_drives_pos": int(np.unique(sid[tem & pos]).size),
                   "test_rows_neg_primary": int((tem & neg_primary).sum()),
                   "test_drives_total": int(np.unique(sid[tem & (pos | neg_primary)]).size),
                   "drives_in_both_train_and_test": int(overlap)})
    folds = pd.DataFrame(fr)
    folds.to_csv(os.path.join(a.out, "drive_heldout_fold_counts.csv"), index=False)

    pd.DataFrame([{"serial_number": s, "reason": r} for s, r in reasons.items()]).to_csv(
        os.path.join(a.out, "quality_excluded_drives.csv"), index=False)

    pd.set_option("display.width", 250)
    print(counts.T.to_string())
    print(folds.to_string(index=False))
    print("quality-excluded drives:", reasons)


if __name__ == "__main__":
    main()
