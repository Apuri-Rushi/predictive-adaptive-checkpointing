"""
Pass 1: compute the 7-day labels for every (drive, day) WITHOUT reading any SMART value.

Label codes (int8):
    1  positive            : t < F <= t+7
    0  negative            : no failure in (t, t+7] and the rule-specific follow-up condition holds
   -1  unknown             : outcome cannot be established -> excluded
   -2  failure day / after : t >= F -> excluded
   -3  quality-excluded drive -> excluded

Primary negative     : the drive has an observation on or after t+7.
Sensitivity negative : the drive has observations on all 7 days t+1 .. t+7.
F = file date of the drive's failure = 1 record.
"""
import numpy as np
import pandas as pd

from config import HORIZON_DAYS, QUALITY_EXCLUDED_SERIALS
from io_utils import daily_files, read_daily

EPOCH = pd.Timestamp("2019-01-01")


def to_day(ts) -> int:
    return int((pd.Timestamp(ts) - EPOCH).days)


def build_label_table():
    """Return (labels DataFrame[sid, day, label_primary, label_sensitivity], serial list)."""
    serial_id, serials, parts = {}, [], []
    for date, path in daily_files():
        df = read_daily(path, ["serial_number", "failure"])
        s = df["serial_number"]
        ids = s.map(serial_id)
        for v in s[ids.isna()].unique():
            serial_id[v] = len(serials)
            serials.append(v)
        parts.append(pd.DataFrame({"sid": s.map(serial_id).astype(np.int32),
                                   "day": np.int16(to_day(date)),
                                   "failure": df["failure"].astype(np.int8)}))
    key = pd.concat(parts, ignore_index=True).sort_values(["sid", "day"], kind="mergesort").reset_index(drop=True)
    serials = np.array(serials, dtype=object)

    sid = key["sid"].to_numpy()
    t = key["day"].to_numpy().astype(np.int64)
    assert not key.duplicated(["sid", "day"]).any(), "duplicate drive-day records"

    fail_day = key.loc[key["failure"] == 1].groupby("sid")["day"].min()
    last_day = key.groupby("sid")["day"].max()
    F = pd.Series(sid).map(fail_day).to_numpy()
    L = pd.Series(sid).map(last_day).to_numpy()
    failed = ~np.isnan(F)
    Fz = np.where(failed, F, 1e9)

    # number of observations of the same drive in (t, t+H]
    comb = sid.astype(np.int64) * 10_000 + t
    n_future = np.searchsorted(comb, comb + HORIZON_DAYS, side="right") - (np.arange(len(comb)) + 1)

    quality = np.isin(serials[sid], list(QUALITY_EXCLUDED_SERIALS))
    after = failed & (t >= Fz)
    pos = failed & (t < Fz) & (Fz - t <= HORIZON_DAYS)
    open_ = ~after & ~pos                               # no failure in (t, t+H]
    neg_p = open_ & (L >= t + HORIZON_DAYS)
    neg_s = open_ & (n_future == HORIZON_DAYS)

    def code(neg):
        c = np.full(len(t), -1, dtype=np.int8)
        c[neg] = 0
        c[pos] = 1
        c[after] = -2
        c[quality] = -3
        return c

    key["label_primary"] = code(neg_p)
    key["label_sensitivity"] = code(neg_s)
    key["failure_day"] = F                              # kept for validation only
    return key.drop(columns="failure"), serials, serial_id
