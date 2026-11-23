"""
Past-only feature construction for one observation day t.

Inputs are the drive's raw SMART values on day t and on earlier days held in a
rolling buffer (days t-7 .. t-1). Nothing dated after t is ever passed to this
module. Missing values stay NaN: there is no zero-filling and no forward-filling
across missing dates.

Per attribute A (20 attributes):
    smart_A_raw         value on day t
    smart_A_raw_prev1   value on day t-1           (NaN if t-1 not observed)
    smart_A_raw_diff1   value(t) - value(t-1)      (NaN unless both days observed and non-missing)
    smart_A_raw_diff7   value(t) - value(t-7)      (NaN unless both days observed and non-missing)
    smart_A_raw_mean7   mean over days t-6 .. t    (NaN unless all 7 days observed and non-missing)
    smart_A_raw_std7    population std over t-6 .. t (same condition as mean7)
Per partial-coverage attribute (187, 188, 190, 240, 241, 242):
    smart_A_raw_missing 1 if the drive did not report A on day t, else 0
                        (taken from the file before the 2019-06-17 masking, so it means
                         "not reported" rather than "damaged")
History:
    n_obs_prev7         number of observed days among t-7 .. t-1
    history_complete_7d 1 if n_obs_prev7 == 7
"""
import numpy as np
import pandas as pd

from config import PARTIAL_ATTRIBUTES, RAW_COLUMNS, ROLL_WINDOW

SUFFIXES = ["", "_prev1", "_diff1", "_diff7", "_mean7", "_std7"]


def feature_names():
    names = [c + s for s in SUFFIXES for c in RAW_COLUMNS]
    names += [f"smart_{a}_raw_missing" for a in PARTIAL_ATTRIBUTES]
    names += ["n_obs_prev7", "history_complete_7d"]
    return names


def build_features(today: pd.DataFrame, buffer: dict, day: int, missing_flags: pd.DataFrame) -> pd.DataFrame:
    """today: raw SMART values for day t, indexed by serial_number (already masked).
    buffer: {day_int: DataFrame indexed by serial_number} for earlier days only.
    missing_flags: 'not reported' indicators for day t (same index as today)."""
    idx = today.index
    x0 = today[RAW_COLUMNS].to_numpy(dtype=np.float64)

    lag_vals, observed = {}, {}
    for k in range(1, 8):
        prev = buffer.get(day - k)
        assert prev is None or max(buffer) < day, "buffer must only contain past days"
        if prev is None:
            observed[k] = np.zeros(len(idx), dtype=bool)
            lag_vals[k] = np.full_like(x0, np.nan)
        else:
            observed[k] = idx.isin(prev.index)
            lag_vals[k] = prev.reindex(idx)[RAW_COLUMNS].to_numpy(dtype=np.float64)

    n_obs = np.sum([observed[k] for k in range(1, 8)], axis=0).astype(np.int16)

    # rolling window t-6 .. t: requires every one of the 6 previous days to be observed
    win = np.stack([x0] + [lag_vals[k] for k in range(1, ROLL_WINDOW)])          # (7, n, A)
    complete_win = np.all([observed[k] for k in range(1, ROLL_WINDOW)], axis=0)  # (n,)
    with np.errstate(invalid="ignore"):
        mean7 = win.mean(axis=0)          # NaN propagates if any value is missing
        std7 = win.std(axis=0)
    mean7[~complete_win] = np.nan
    std7[~complete_win] = np.nan

    blocks = {
        "": x0,
        "_prev1": lag_vals[1],
        "_diff1": x0 - lag_vals[1],
        "_diff7": x0 - lag_vals[7],
        "_mean7": mean7,
        "_std7": std7,
    }
    cols = {}
    for s in SUFFIXES:
        for j, c in enumerate(RAW_COLUMNS):
            cols[c + s] = blocks[s][:, j]
    out = pd.DataFrame(cols, index=idx)
    for a in PARTIAL_ATTRIBUTES:
        out[f"smart_{a}_raw_missing"] = missing_flags[f"smart_{a}_raw"].astype(np.int8).to_numpy()
    out["n_obs_prev7"] = n_obs
    out["history_complete_7d"] = (n_obs == 7).astype(np.int8)
    return out[feature_names()]
