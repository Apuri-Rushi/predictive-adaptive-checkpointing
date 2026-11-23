"""
Deterministic, stratified negative sampling of the training file (training data only).

* All positive rows (label_primary == 1) are kept.
* Exactly NEG_PER_POS x (#positives) negatives are drawn. The quota is allocated across
  (date x model) strata in proportion to each stratum's number of negatives (largest-remainder
  rounding). Within a stratum, the rows with the smallest crc32("<seed>|<serial>|<date>") are
  taken, ties broken by file row order. The draw therefore depends only on the seed and the
  row identities, not on chunk sizes or read order.
* Two passes over train_chronological.csv.gz: (1) light columns only, to decide; (2) extract
  the selected rows with all features. Peak memory stays far below the 3 GB budget.
"""
import zlib

import numpy as np
import pandas as pd

from rf_config import CHUNK, FEATURES, LABEL, NEG_PER_POS, SEED, STRATA, TRAIN_FILE

META = ["serial_number", "date", "model"]


def _keys(serials, dates):
    return np.fromiter((zlib.crc32(f"{SEED}|{s}|{d}".encode()) for s, d in zip(serials, dates)),
                       dtype=np.uint32, count=len(serials))


def plan_sample(log):
    """Pass 1: decide which file rows are sampled. Returns (selected_row_mask, sampling_info)."""
    parts = []
    offset = 0
    date_code, model_code = {}, {}            # strings -> small ints (keeps pass-1 memory low)
    for ch in pd.read_csv(TRAIN_FILE, usecols=META + [LABEL], chunksize=1_000_000,
                          dtype={"serial_number": str, "date": str, "model": str, LABEL: "int8"}):
        for v in ch["date"].unique():
            date_code.setdefault(v, len(date_code))
        for v in ch["model"].unique():
            model_code.setdefault(v, len(model_code))
        parts.append(pd.DataFrame({"row": np.arange(offset, offset + len(ch), dtype=np.int64),
                                   "date": ch["date"].map(date_code).to_numpy(np.int16),
                                   "model": ch["model"].map(model_code).to_numpy(np.int16),
                                   "y": ch[LABEL].to_numpy(),
                                   "key": _keys(ch["serial_number"].to_numpy(), ch["date"].to_numpy())}))
        offset += len(ch)
    df = pd.concat(parts, ignore_index=True)
    del parts
    inv_date = {v: k for k, v in date_code.items()}
    inv_model = {v: k for k, v in model_code.items()}
    n_pos = int((df["y"] == 1).sum())
    neg = df[df["y"] == 0]
    target = NEG_PER_POS * n_pos

    # proportional allocation with largest-remainder rounding (sums exactly to target)
    sizes = neg.groupby(STRATA).size()
    exact = sizes * target / sizes.sum()
    quota = np.floor(exact).astype(int)
    short = target - int(quota.sum())
    if short:
        quota.loc[(exact - quota).sort_values(ascending=False, kind="mergesort").index[:short]] += 1
    assert int(quota.sum()) == target

    neg = neg.sort_values(STRATA + ["key", "row"], kind="mergesort")
    neg["rank"] = neg.groupby(STRATA).cumcount()
    neg = neg.join(quota.rename("quota"), on=STRATA)
    chosen = neg.loc[neg["rank"] < neg["quota"], "row"].to_numpy()

    mask = np.zeros(offset, dtype=bool)
    mask[chosen] = True
    mask[df.loc[df["y"] == 1, "row"].to_numpy()] = True

    # distribution check: sampled vs population negative shares by date and by model
    samp = neg[neg["rank"] < neg["quota"]]
    by_date = pd.DataFrame({"population_share": neg.groupby("date").size() / len(neg),
                            "sample_share": samp.groupby("date").size() / len(samp)}).fillna(0)
    by_model = pd.DataFrame({"population_share": neg.groupby("model").size() / len(neg),
                             "sample_share": samp.groupby("model").size() / len(samp)}).fillna(0)
    by_date.index = by_date.index.map(inv_date)
    by_model.index = by_model.index.map(inv_model)
    by_date = by_date.sort_index()
    info = {"seed": SEED, "neg_per_pos": NEG_PER_POS, "strata": STRATA,
            "train_rows_total": int(offset), "positives_total": n_pos, "negatives_total": int(len(neg)),
            "negatives_sampled": int(len(chosen)), "strata_count": int(len(sizes)),
            "strata_with_zero_quota": int((quota == 0).sum()),
            "max_abs_share_diff_by_date": float((by_date["population_share"] - by_date["sample_share"]).abs().max()),
            "max_abs_share_diff_by_model": float((by_model["population_share"] - by_model["sample_share"]).abs().max()),
            "negatives_total_by_date": {inv_date[k]: int(v) for k, v in neg.groupby("date").size().items()},
            "negatives_sampled_by_date": {inv_date[k]: int(v) for k, v in samp.groupby("date").size().items()}}
    log(f"  sampling plan: {n_pos:,} positives, {len(chosen):,} of {len(neg):,} negatives "
        f"across {len(sizes):,} date x model strata")
    return mask, info, by_date, by_model


def extract_sample(mask, log):
    """Pass 2: read the selected rows with all features (float32) and metadata."""
    dtypes = {f: "float32" for f in FEATURES}
    dtypes.update({"serial_number": str, "date": str, "model": str, LABEL: "int8"})
    out, offset = [], 0
    for ch in pd.read_csv(TRAIN_FILE, usecols=META + FEATURES + [LABEL], dtype=dtypes, chunksize=CHUNK):
        m = mask[offset:offset + len(ch)]
        if m.any():
            out.append(ch.loc[m, META + FEATURES + [LABEL]])
        offset += len(ch)
    s = pd.concat(out, ignore_index=True)
    s["date"] = pd.to_datetime(s["date"])
    log(f"  extracted {len(s):,} sampled rows")
    return s
