#!/usr/bin/env python
"""
Independent validation of a complete multi-shard run (results/full_rho<ρ>/), shard by shard.

Per shard (single-run checks; determinism was established by the pilot and is spot-checked separately):
  H  integrity: DONE marker present; OUTPUT_SHA256.txt matches freshly computed hashes
  1  hosts = independent crc32(serial) % 56 shard membership; score counts / first days match
  2/3 tier timeline = independent recomputation (score of day d in force from day d+1; carry-forward)
  4  injector failures = independent recomputation from drive_failure_summary.csv
  5  workload.csv = independent regeneration (ids, lengths, submit times with this run's ρ);
     every policy run processed exactly that job set (ids, stream/host, length, submit)
  6  overhead = 300 s x checkpoints = checkpoint-log count per job
  7  replacement ready at failure + D + B; restore completed at + D + B + R when a checkpoint existed
  8  lost work = time since last completed checkpoint (or job start); committed = last checkpoint
  9  replacement hosts distinct, >= n, never failed; jobs after the failure run on the spare
  10 deadline = submit + 1.5 L; state consistent with finish
  11 planned == submitted == finished; only terminal states
  F  FIFO / one job at a time / never before submit
  A  turnaround = queue + L + overhead + lost + interrupted write + recovery (residual bounded)
Writes <run>/validation/{validation_by_shard.csv, validation_summary.json}

Usage (from project/cloudsim):  python -I research/validation/validate_full.py results/full_rho0.9 [--workers 3]
"""
import argparse
import concurrent.futures as cf
import gzip
import hashlib
import json
import os
import zlib

import numpy as np
import pandas as pd

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PRED = os.path.join(PROJ, "ml", "results", "model_evaluation", "test_predictions.csv.gz")
FAILS = os.path.join(PROJ, "ml", "results", "dataset_audit_revalidation", "drive_failure_summary.csv")
DAY, C, R, D, B, DEADLINE, CUTOFF = 86400.0, 300.0, 300.0, 60.0, 120.0, 1.5, 30 * 86400.0
LOW_UPPER, HIGH_LOWER = 0.000234, 0.001732
TOL = 2.0
RUNS = ["E1_none"] + [f"E2_fixed_T0_{t}h" for t in (1, 4, 12, 24, 72)] + [f"E3_adaptive_T0_{t}h" for t in (1, 4, 12, 24, 72)]


def crc(s):
    return zlib.crc32(s.encode("utf-8"))


def sha_file(p):
    h = hashlib.sha256()
    with (gzip.open if p.endswith(".gz") else open)(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tier_of(x):
    return np.where(np.isnan(x), "MEDIUM", np.where(x < LOW_UPPER, "LOW", np.where(x < HIGH_LOWER, "MEDIUM", "HIGH")))


def length_of(serial, j):
    v = crc(f"{serial}|{j}") % 10
    return 24 * 3600.0 if v <= 4 else 72 * 3600.0 if v <= 7 else 168 * 3600.0


def validate_shard(args):
    run_dir, k, shards, rho, pred_k, fails_k = args
    d = os.path.join(run_dir, f"shard_{k:02d}")
    res = {"shard": k}
    ok = lambda key, cond: res.__setitem__(key, bool(cond))
    # H integrity
    ok("H_done_marker", os.path.exists(os.path.join(d, "DONE")))
    want = {}
    for line in open(os.path.join(d, "OUTPUT_SHA256.txt")).read().splitlines():
        h, rel = line.split("  ", 1)
        want[rel] = h
    ok("H_hashes_match", all(sha_file(os.path.join(d, rel)) == h for rel, h in want.items()))
    # 1 hosts
    serials = sorted(pred_k["serial_number"].unique())
    st = pd.read_csv(os.path.join(d, "streams.csv"), dtype={"serial": str})
    fd = pred_k.groupby("serial_number")["day"].min()
    sc = pred_k.groupby("serial_number").size()
    ok("1_hosts", list(st["serial"]) == serials and (st["primary_host"] == st["stream"]).all()
       and (st["score_count"].values == sc.reindex(serials).values).all()
       and (st["first_day"].values == fd.reindex(serials).values).all())
    n = len(serials)
    stream_of = {s: i for i, s in enumerate(serials)}
    # 2/3 tier timeline (vectorised as-of join: latest score dated <= d-1)
    tl = pd.read_csv(os.path.join(d, "tier_timeline.csv"), dtype={"serial": str})
    q = tl[["serial", "day"]].copy()
    q["key"] = q["day"] - 1
    sc_tab = pred_k.rename(columns={"serial_number": "serial", "day": "key"})[["serial", "key", "p_failure_7d_corrected"]]
    m = pd.merge_asof(q.sort_values("key"), sc_tab.sort_values("key"), on="key", by="serial", direction="backward")
    m = m.set_index(["serial", "day"]).reindex(pd.MultiIndex.from_frame(tl[["serial", "day"]]))
    exp = m["p_failure_7d_corrected"].to_numpy()
    got = tl["score_in_force"].to_numpy()
    same_nan = np.isnan(exp) == np.isnan(got)
    close = np.where(np.isnan(exp), True, np.abs(np.nan_to_num(got) - np.nan_to_num(exp)) <= 1e-9 * np.maximum(1, np.nan_to_num(exp)))
    ok("2_no_lookahead_scores", same_nan.all() and close.all())
    ok("3_tiers_carry_forward", (tier_of(exp) == tl["tier"].to_numpy()).all())
    # 4 failures
    inj = pd.read_csv(os.path.join(d, "injector_failures.csv"))
    exp_f = sorted((stream_of[s], (pd.Timestamp(dt_) - pd.Timestamp("2019-06-01")).days * DAY + crc("fail|" + s) % 86400)
                   for s, dt_ in zip(fails_k["serial_number"], fails_k["failure_date"]))
    got_f = sorted(zip(inj["stream"], inj["t_fail"]))
    ok("4_failures", len(exp_f) == len(got_f) and all(a[0] == b[0] and abs(a[1] - b[1]) < 0.05 for a, b in zip(exp_f, got_f)))
    fail_time = dict(zip(inj["stream"], inj["t_fail"]))
    # 5 workload
    wl = pd.read_csv(os.path.join(d, "workload.csv"), dtype={"serial": str})
    rows = []
    for s in serials:
        t, j = max(0, int(fd[s])) * DAY, 0
        while t < CUTOFF:
            L = length_of(s, j)
            rows.append((f"{s}#{j}", L, t))
            t += L / rho
            j += 1
    ew = pd.DataFrame(rows, columns=["job_id", "length_sec", "submit_time"])
    ok("5a_workload_regenerated", len(wl) == len(ew) and (wl["job_id"].values == ew["job_id"].values).all()
       and np.allclose(wl["length_sec"], ew["length_sec"]) and np.allclose(wl["submit_time"], ew["submit_time"], atol=0.01)
       and (wl["primary_host"] == wl["stream"]).all())
    key = wl.set_index("job_id")[["stream", "length_sec", "submit_time"]].sort_index()
    res["planned_jobs"] = len(wl)
    res["failures"] = len(inj)
    flags = {x: True for x in ("5b_same_job_set", "6_overhead", "7_recovery", "8_lost_work", "9_replacement",
                               "10_deadline", "11_terminal", "F_fifo", "A_accounting")}
    for r in RUNS:
        rd = os.path.join(d, r)
        j = pd.read_csv(os.path.join(rd, "jobs.csv"), dtype={"serial": str})
        ri = json.load(open(os.path.join(rd, "run_info.json")))
        flags["5b_same_job_set"] &= j.set_index("job_id")[["stream", "length_sec", "submit_time"]].sort_index().equals(key) \
            and ri["workload_sha256"] == json.load(open(os.path.join(d, "inputs.json")))["workload_sha256"]
        # 6 overhead (count checkpoints per job from the log, chunked)
        cnt = None
        for ch in pd.read_csv(os.path.join(rd, "checkpoint_events.csv.gz"), usecols=["stream", "job"], chunksize=2_000_000):
            vc = ch.groupby(["stream", "job"]).size()
            cnt = vc if cnt is None else cnt.add(vc, fill_value=0)
        jj = j.set_index(["stream", "job"])
        cnt = (cnt if cnt is not None else pd.Series(dtype=float)).reindex(jj.index, fill_value=0)
        flags["6_overhead"] &= bool((jj["checkpoint_overhead_sec"] == jj["checkpoints"] * C).all()
                                    and (cnt.astype(int) == jj["checkpoints"]).all())
        # 7/8/9 failures
        fe = pd.read_csv(os.path.join(rd, "failure_events.csv"))
        rc = pd.read_csv(os.path.join(rd, "recovery_events.csv"))
        fstreams = set(fe["stream"])
        ck = pd.concat([ch[ch["stream"].isin(fstreams)] for ch in
                        pd.read_csv(os.path.join(rd, "checkpoint_events.csv.gz"), chunksize=2_000_000)]) if fstreams else None
        for f in fe.itertuples():
            rr = rc[(rc["stream"] == f.stream) & (rc["time"] > f.time - 1e-6)]
            ready = rr[rr["event"].str.startswith("replacement_ready")]
            flags["7_recovery"] &= len(ready) >= 1 and abs(ready["time"].iloc[0] - f.time - (D + B)) < 0.01
            if f.phase == "IDLE":
                flags["8_lost_work"] &= f.lost_sec == 0
            else:
                if f.committed_sec > 0:
                    done = rr[rr["event"] == "restore_completed"]
                    flags["7_recovery"] &= len(done) >= 1 and abs(done["time"].iloc[0] - f.time - (D + B + R)) < TOL
                # <= : a checkpoint completing at the same instant as the failure is processed first
                # by CloudSim (equal-time events) and is therefore committed (lost work = 0)
                prev = ck[(ck["stream"] == f.stream) & (ck["job"] == f.job) & (ck["time"] <= f.time)]
                last = prev["committed_work_sec"].iloc[-1] if len(prev) else 0.0
                flags["8_lost_work"] &= abs(f.committed_sec - last) < 0.01 and \
                    abs(f.lost_sec - (f.progress_at_failure_sec - f.committed_sec)) < 0.01
                if f.phase == "RUN":
                    since = prev["time"].iloc[-1] if len(prev) else jj.loc[(f.stream, f.job), "start_time"]
                    flags["8_lost_work"] &= abs(f.lost_sec - (f.time - since)) < TOL + 0.6
            js = j[j["stream"] == f.stream]
            flags["9_replacement"] &= all(str(h) == str(f.replacement_vm)
                                          for h in js.loc[js["start_time"] > f.time, "hosts_used"].astype(str))
        flags["9_replacement"] &= bool(len(fe) == len(fail_time) and set(fe["stream"]) == set(fail_time)
                                       and (fe["replacement_vm"] >= n).all() and fe["replacement_vm"].is_unique
                                       and "=1" not in [x for x in open(os.path.join(rd, "hosts.csv")).read().splitlines()
                                                        if x.startswith("# spare")][0])
        # 10 / 11 / F / A
        flags["10_deadline"] &= bool((abs(j["deadline"] - (j["submit_time"] + DEADLINE * j["length_sec"])) < 0.01).all()
                                     and ((j["finish_time"] <= j["deadline"] + 1e-3).astype(int) == j["success"]).all()
                                     and ((j["state"] == "COMPLETED_ON_TIME") == (j["success"] == 1)).all())
        flags["11_terminal"] &= bool(j["state"].isin(["COMPLETED_ON_TIME", "COMPLETED_LATE"]).all()
                                     and ri["jobs_planned"] == ri["jobs_submitted"] == len(wl)
                                     and ri["failures_fired"] == ri["failures_scheduled"] == len(fail_time))
        g = j.sort_values(["stream", "job"])
        same_stream = g["stream"].values[1:] == g["stream"].values[:-1]
        flags["F_fifo"] &= bool((j["start_time"] >= j["submit_time"] - 1e-6).all()
                                and (g["start_time"].values[1:][same_stream] >= g["finish_time"].values[:-1][same_stream] - 1e-6).all())
        resid = j["turnaround_sec"] - (j["queue_delay_sec"] + j["length_sec"] + j["checkpoint_overhead_sec"]
                                       + j["lost_work_sec"] + j["interrupted_write_sec"] + j["recovery_sec"])
        bound = 0.1 * (j["length_sec"] / 3600 * 3 + 40) + 1
        flags["A_accounting"] &= bool((resid >= -0.5).all() and (resid <= bound).all())
        res[f"max_residual_{r}"] = round(float(resid.max()), 3)
    res.update(flags)
    # every check flag is a (numpy or python) bool; count them all
    res = {kk: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for kk, v in res.items()}
    res["all_pass"] = all(v for kk, v in res.items() if isinstance(v, bool))
    print(f"shard {k:02d}: {'PASS' if res['all_pass'] else 'FAIL ' + str([x for x, v in res.items() if v is False])}",
          flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="", help="comma-separated shard subset (testing)")
    a = ap.parse_args()
    subset = [int(x) for x in a.only.split(",")] if a.only else list(range(int(json.load(
        open(os.path.join(a.run_dir, "run_config.json")))["shards"])))
    cfg = json.load(open(os.path.join(a.run_dir, "run_config.json")))
    shards, rho = int(cfg["shards"]), float(cfg["utilization"])
    man = pd.read_csv(os.path.join(a.run_dir, "manifest.csv"))
    pred = pd.read_csv(PRED, usecols=["serial_number", "date", "p_failure_7d_corrected"], dtype={"serial_number": str})
    pred["day"] = (pd.to_datetime(pred["date"]) - pd.Timestamp("2019-06-01")).dt.days
    pred["shard"] = pred["serial_number"].map(lambda s: crc(s) % shards)
    fs = pd.read_csv(FAILS, dtype={"serial_number": str})
    fs = fs[(fs["failure_date"] >= "2019-06-01") & (fs["failure_date"] <= "2019-06-30")
            & fs["serial_number"].isin(set(pred["serial_number"]))]
    fs["shard"] = fs["serial_number"].map(lambda s: crc(s) % shards)
    jobs = [(a.run_dir, k, shards, rho, pred[pred["shard"] == k].drop(columns=["date", "shard"]), fs[fs["shard"] == k])
            for k in subset]
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(validate_shard, jobs))
    df = pd.DataFrame(out).sort_values("shard")
    vdir = os.path.join(a.run_dir, "validation")
    os.makedirs(vdir, exist_ok=True)
    df.to_csv(os.path.join(vdir, "validation_by_shard.csv"), index=False)
    done = man[man["status"] == "DONE"].drop_duplicates("shard", keep="last")
    summary = {"run_dir": a.run_dir, "utilization": rho, "shards_expected": shards,
               "shards_done_in_manifest": int(done["shard"].nunique()),
               "shards_validated": int(len(df)), "shards_all_pass": int(df["all_pass"].sum()),
               "failed_checks": {c: [int(s) for s in df.loc[~df[c], "shard"]] for c in df.columns
                                 if df[c].dtype == bool and (~df[c]).any()},
               "total_hosts_planned_jobs": int(df["planned_jobs"].sum()), "total_failures": int(df["failures"].sum()),
               "independent_total_june_failures_in_pool": int(len(fs)),
               "total_wall_hours": round(float(done["wall_seconds"].sum()) / 3600, 2),
               "max_peak_heap_mb": int(done["max_peak_heap_mb"].max())}
    if a.only:
        summary["note"] = "subset run (--only): totals and pass criteria cover the subset only"
        summary["all_pass"] = summary["shards_all_pass"] == len(subset)
    else:
        summary["all_pass"] = summary["shards_all_pass"] == shards == summary["shards_done_in_manifest"] and \
            summary["total_failures"] == summary["independent_total_june_failures_in_pool"]
    json.dump(summary, open(os.path.join(vdir, "validation_summary.json"), "w"), indent=2)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
