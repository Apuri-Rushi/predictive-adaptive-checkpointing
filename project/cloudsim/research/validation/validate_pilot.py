#!/usr/bin/env python
"""
Independent validation of a trace-driven CloudSim shard run (predetermined-workload version).

Recomputes everything it can from the RAW inputs (test_predictions.csv.gz, drive_failure_summary.csv)
without using any Java code, then checks the simulator outputs.

Usage (from project/cloudsim):
    python -I research/validation/validate_pilot.py <pilot_dir> [shard] [shards]
Expects <pilot_dir>/run1, run2, check_labels_scrambled, check_no_failures.
Writes <pilot_dir>/validation/{validation_results.json, pilot_summary.csv, per_failure.csv,
                                tier_occupancy.csv, checkpoints_by_tier.csv}
"""
import gzip
import json
import os
import sys
import zlib
from datetime import date

import pandas as pd

PILOT = sys.argv[1] if len(sys.argv) > 1 else "results/pilot"
SHARD = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SHARDS = int(sys.argv[3]) if len(sys.argv) > 3 else 56
PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))       # .../project
PRED = os.path.join(PROJ, "ml", "results", "model_evaluation", "test_predictions.csv.gz")
FAILS = os.path.join(PROJ, "ml", "results", "dataset_audit_revalidation", "drive_failure_summary.csv")
SRC = os.path.join(PROJ, "cloudsim", "research", "src")
DAY, C, R, D, B, DEADLINE, CUTOFF = 86400.0, 300.0, 300.0, 60.0, 120.0, 1.5, 30 * 86400.0
LOW_UPPER, HIGH_LOWER = 0.000234, 0.001732
HOSTS_PER_DC = 50
TOL = 2.0              # seconds: CloudSim start-up offset (0.1 s) + event granularity
RUN1, RUN2 = os.path.join(PILOT, "run1"), os.path.join(PILOT, "run2")
OUT = os.path.join(PILOT, "validation")
os.makedirs(OUT, exist_ok=True)
results = {}


def check(key, ok, detail=""):
    results[key] = {"pass": bool(ok), "detail": str(detail)}
    print(f"[{'PASS' if ok else 'FAIL'}] {key}  {detail}", flush=True)


def crc(s):
    return zlib.crc32(s.encode("utf-8"))


def runs_in(d):
    return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)) and x[:2] in ("E1", "E2", "E3"))


def tier(score):
    if score is None or pd.isna(score):
        return "MEDIUM"
    return "LOW" if score < LOW_UPPER else ("MEDIUM" if score < HIGH_LOWER else "HIGH")


def length_of(serial, j):
    v = crc(f"{serial}|{j}") % 10
    return 24 * 3600.0 if v <= 4 else 72 * 3600.0 if v <= 7 else 168 * 3600.0


# ====================================================================== independent input reconstruction
pred = pd.read_csv(PRED, usecols=["serial_number", "date", "p_failure_7d_corrected"],
                   dtype={"serial_number": str, "date": str})
pred = pred[pred["serial_number"].map(lambda s: crc(s) % SHARDS == SHARD)].copy()
pred["day"] = (pd.to_datetime(pred["date"]) - pd.Timestamp("2019-06-01")).dt.days
serials = sorted(pred["serial_number"].unique())
stream_of = {s: i for i, s in enumerate(serials)}
streams = pd.read_csv(os.path.join(RUN1, "streams.csv"), dtype={"serial": str})

# 1. hosts loaded
check("1_hosts_loaded_match_independent_shard",
      list(streams["serial"]) == serials and (streams["primary_host"] == streams["stream"]).all(),
      f"{len(serials)} hosts; independent={len(serials)} java={len(streams)}")
sc = pred.groupby("serial_number").size()
fd = pred.groupby("serial_number")["day"].min()
check("1_score_counts_and_first_days_match",
      (streams.set_index("serial")["score_count"] == sc.reindex(streams["serial"]).values).all()
      and (streams.set_index("serial")["first_day"] == fd.reindex(streams["serial"]).values).all(),
      f"{len(pred)} score rows in shard")

# 2/3. prediction timing + carry-forward
tl = pd.read_csv(os.path.join(RUN1, "tier_timeline.csv"), dtype={"serial": str})
by = {s: g.set_index("day")["p_failure_7d_corrected"].sort_index() for s, g in pred.groupby("serial_number")}
mism_tier = mism_score = carried = lookahead = 0
for row in tl.itertuples(index=False):
    ser = by[row.serial]
    avail = ser[ser.index <= row.day - 1]
    exp_score = avail.iloc[-1] if len(avail) else None
    if exp_score is not None and (row.day - 1) not in ser.index:
        carried += 1
    got = row.score_in_force if not pd.isna(row.score_in_force) else None
    if (exp_score is None) != (got is None) or (got is not None and abs(got - exp_score) > 1e-9 * max(1, exp_score)):
        mism_score += 1
    if tier(exp_score) != row.tier:
        mism_tier += 1
    fut = ser[ser.index >= row.day]
    if got is not None and any(abs(fut - got) < 1e-15) and not any(abs(avail - got) < 1e-15):
        lookahead += 1
check("2_prediction_applied_from_day_d_plus_1_no_lookahead", mism_score == 0 and lookahead == 0,
      f"{len(tl)} host-days; score mismatches={mism_score}; look-ahead={lookahead}")
check("3_missing_days_use_last_available_score", mism_tier == 0 and carried > 0,
      f"tier mismatches={mism_tier}; carried-forward host-days={carried}")

# 4. failure dates only through the injector
fs = pd.read_csv(FAILS, dtype={"serial_number": str})
fs = fs[fs["serial_number"].isin(stream_of) & (fs["failure_date"] >= "2019-06-01") & (fs["failure_date"] <= "2019-06-30")]
exp_f = sorted((stream_of[s], (date.fromisoformat(d) - date(2019, 6, 1)).days * DAY + crc("fail|" + s) % 86400)
               for s, d in zip(fs["serial_number"], fs["failure_date"]))
inj = pd.read_csv(os.path.join(RUN1, "injector_failures.csv"))
got_f = sorted(zip(inj["stream"], inj["t_fail"]))
check("4a_injector_failures_match_independent_trace",
      len(exp_f) == len(got_f) and all(a[0] == b[0] and abs(a[1] - b[1]) < 0.05 for a, b in zip(exp_f, got_f)),
      f"{len(exp_f)} failures")
broker_src = open(os.path.join(SRC, "ckpt", "sim", "CheckpointingBroker.java"), encoding="utf-8").read()
policy_src = "".join(open(os.path.join(SRC, "ckpt", "policy", f), encoding="utf-8").read()
                     for f in os.listdir(os.path.join(SRC, "ckpt", "policy")))
check("4b_failure_data_not_visible_to_broker_or_policies",
      "FailureEvent" not in broker_src and "FailureTraceLoader" not in broker_src
      and "FailureEvent" not in policy_src and "FailureTraceLoader" not in policy_src,
      "broker and policy sources never reference FailureEvent / FailureTraceLoader")
fail_time = dict(zip(inj["stream"], inj["t_fail"]))
first_fail = min(fail_time.values()) if fail_time else float("inf")
coupled_from = {}
for s, t in fail_time.items():
    coupled_from[s // HOSTS_PER_DC] = min(coupled_from.get(s // HOSTS_PER_DC, float("inf")), t)
for h in range(len(serials), len(serials) + len(fail_time) + 1):
    coupled_from[h // HOSTS_PER_DC] = min(coupled_from.get(h // HOSTS_PER_DC, float("inf")), first_fail)
w_ck = pd.read_csv(os.path.join(RUN1, "E3_adaptive_T0_4h", "checkpoint_events.csv.gz"))
n_ck = pd.read_csv(os.path.join(PILOT, "check_no_failures", "E3_adaptive_T0_4h", "checkpoint_events.csv.gz"))
v_first = v_out = v_cnt = v_tier = 0
max_shift = 0.0
differing = set()
cols = ["time", "job", "committed_work_sec", "tier"]
for s in sorted(set(w_ck["stream"]) | set(n_ck["stream"])):
    a = w_ck[w_ck["stream"] == s].reset_index(drop=True)
    b = n_ck[n_ck["stream"] == s].reset_index(drop=True)
    if a[cols].equals(b[cols]):
        continue
    differing.add(s)
    if not a[a["time"] < first_fail][cols].reset_index(drop=True).equals(b[b["time"] < first_fail][cols].reset_index(drop=True)):
        v_first += 1
    dc = s // HOSTS_PER_DC
    if dc not in coupled_from or not a[a["time"] < coupled_from[dc]][cols].reset_index(drop=True).equals(
            b[b["time"] < coupled_from[dc]][cols].reset_index(drop=True)):
        v_out += 1
        continue
    if s not in fail_time:
        v_cnt += 0 if a.groupby("job").size().equals(b.groupby("job").size()) else 1
        v_tier += 0 if a["tier"].reset_index(drop=True).equals(b["tier"].reset_index(drop=True)) else 1
        k = min(len(a), len(b))
        max_shift = max(max_shift, float((a["time"][:k] - b["time"][:k]).abs().max()))
check("4c_no_failure_information_before_failure",
      v_first == 0 and v_out == 0 and v_cnt == 0 and v_tier == 0 and max_shift <= 0.5,
      f"E3 T0=4h with vs without failure trace: diffs before first failure={v_first}; outside coupled "
      f"datacenters={v_out}; non-failing hosts with changed checkpoint counts={v_cnt}, tiers={v_tier}; "
      f"max jitter={max_shift:.3f}s; {len(differing)} streams with jitter in datacenters "
      f"{sorted({s // HOSTS_PER_DC for s in differing})}")

# 5. common predetermined workload
wl = pd.read_csv(os.path.join(RUN1, "workload.csv"), dtype={"serial": str})
exp_rows = []
for s in serials:
    t = max(0, int(fd[s])) * DAY
    j = 0
    while t < CUTOFF:
        L = length_of(s, j)
        exp_rows.append((f"{s}#{j}", stream_of[s], s, j, L, t))
        t += L
        j += 1
exp_wl = pd.DataFrame(exp_rows, columns=["job_id", "stream", "serial", "job_index", "length_sec", "submit_time"])
wl_ok = len(wl) == len(exp_wl) and (wl["job_id"].values == exp_wl["job_id"].values).all() \
    and (abs(wl["length_sec"].values - exp_wl["length_sec"].values) < 1e-6).all() \
    and (abs(wl["submit_time"].values - exp_wl["submit_time"].values) < 0.01).all() \
    and (wl["primary_host"] == wl["stream"]).all()
check("5a_workload_plan_matches_independent_regeneration", wl_ok,
      f"{len(wl)} planned jobs; ids, lengths (24/72/168 h mix), nominal back-to-back submit times < 30-day cutoff")
hashes = set()
for d in (RUN1, RUN2):
    for r in runs_in(d):
        ri = json.load(open(os.path.join(d, r, "run_info.json")))
        hashes.add((ri["workload_sha256"], ri["failures_sha256"], ri["tier_timeline_sha256"]))
jobs_all = {r: pd.read_csv(os.path.join(RUN1, r, "jobs.csv"), dtype={"serial": str}) for r in runs_in(RUN1)}
key = wl.set_index("job_id")[["stream", "length_sec", "submit_time"]].sort_index()
same_set = all(j.set_index("job_id")[["stream", "length_sec", "submit_time"]].sort_index().equals(key)
               for j in jobs_all.values())
check("5b_identical_job_ids_lengths_submits_hosts_for_all_policies", len(hashes) == 1 and same_set,
      f"{len(jobs_all)} policy runs x 2 repeats: one (workload, failure, tier) hash; every run processed exactly "
      f"the {len(wl)} planned jobs with identical stream/host, length and submit time")

# per-run checks
per_fail, summ = [], []
agg = {k: True for k in ("6", "7", "8", "9", "10", "11", "fifo", "id")}
resid_txt = []
ck_tier_rows = []
for r in runs_in(RUN1):
    d = os.path.join(RUN1, r)
    j = jobs_all[r]
    ck = pd.read_csv(os.path.join(d, "checkpoint_events.csv.gz"))
    fe = pd.read_csv(os.path.join(d, "failure_events.csv"))
    rc = pd.read_csv(os.path.join(d, "recovery_events.csv"))
    ri = json.load(open(os.path.join(d, "run_info.json")))
    hosts_txt = open(os.path.join(d, "hosts.csv")).read().splitlines()
    n = len(serials)
    jj = j.set_index(["stream", "job"])
    # 6. overhead
    ckn = ck.groupby(["stream", "job"]).size()
    ok6 = (jj["checkpoint_overhead_sec"] == jj["checkpoints"] * C).all() and \
        (ckn.reindex(jj.index, fill_value=0) == jj["checkpoints"]).all()
    if r == "E1_none":
        ok6 &= int(jj["checkpoints"].sum()) == 0
    agg["6"] &= bool(ok6)
    # 7. recovery timing
    ok7 = True
    for f in fe.itertuples():
        rr = rc[(rc["stream"] == f.stream) & (rc["time"] > f.time - 1e-6)]
        ready = rr[rr["event"].str.startswith("replacement_ready")]
        ok7 &= len(ready) >= 1 and abs(ready["time"].iloc[0] - f.time - (D + B)) < 0.01
        if f.phase == "IDLE":
            ok7 &= ready["event"].iloc[0] == "replacement_ready_idle"
            continue
        if f.committed_sec > 0:
            done = rr[rr["event"] == "restore_completed"]
            ok7 &= len(done) >= 1 and abs(done["time"].iloc[0] - f.time - (D + B + R)) < TOL
        jr = jj.loc[(f.stream, f.job)]
        if jr["failures"] == 1:
            ok7 &= abs(jr["recovery_sec"] - ((D + B + R) if f.committed_sec > 0 else (D + B))) < 1e-6
    agg["7"] &= bool(ok7)
    # 8. lost work
    ok8 = True
    for f in fe.itertuples():
        if f.phase == "IDLE":
            ok8 &= f.lost_sec == 0
        else:
            prev = ck[(ck["stream"] == f.stream) & (ck["job"] == f.job) & (ck["time"] < f.time)]
            last_commit = prev["committed_work_sec"].iloc[-1] if len(prev) else 0.0
            ok8 &= abs(f.committed_sec - last_commit) < 0.01
            ok8 &= abs(f.lost_sec - (f.progress_at_failure_sec - f.committed_sec)) < 0.01
            if f.phase == "RUN":
                since = prev["time"].iloc[-1] if len(prev) else jj.loc[(f.stream, f.job), "start_time"]
                ok8 &= abs(f.lost_sec - (f.time - since)) < TOL + 0.6
        per_fail.append({"run": r, "stream": f.stream, "serial": serials[f.stream], "job": f.job, "time": f.time,
                         "phase": f.phase, "committed_sec": f.committed_sec, "lost_sec": f.lost_sec,
                         "failed_vm": f.failed_vm, "replacement_vm": f.replacement_vm})
    agg["8"] &= bool(ok8)
    # 9. replacement hosts
    reps = fe["replacement_vm"].tolist()
    ok9 = all(v >= n for v in reps) and len(set(reps)) == len(reps) and (fe["failed_vm"] == fe["stream"]).all()
    for f in fe.itertuples():
        js = j[j["stream"] == f.stream]
        after = js[js["start_time"] > f.time]
        ok9 &= all(str(h) == str(f.replacement_vm) for h in after["hosts_used"].astype(str))
        before_done = js[js["finish_time"] <= f.time]
        ok9 &= all(str(h) == str(f.stream) for h in before_done["hosts_used"].astype(str))
        if f.phase != "IDLE":
            ok9 &= str(jj.loc[(f.stream, f.job), "hosts_used"]).split(";") == [str(f.stream), str(f.replacement_vm)]
    spare_line = [x for x in hosts_txt if x.startswith("# spare")][0]
    ok9 &= "=1" not in spare_line
    hd = pd.read_csv(os.path.join(d, "hosts.csv"), comment="#")
    ok9 &= set(hd.loc[hd["primary_host_failed_flag"] == 1, "stream"]) == set(inj["stream"])
    agg["9"] &= bool(ok9)
    # 10. deadlines
    ok10 = (abs(j["deadline"] - (j["submit_time"] + DEADLINE * j["length_sec"])) < 0.01).all()
    exp_succ = (j["finish_time"] <= j["deadline"] + 1e-3).astype(int)
    ok10 &= (exp_succ == j["success"]).all()
    ok10 &= ((j["state"] == "COMPLETED_ON_TIME") == (j["success"] == 1)).all()
    agg["10"] &= bool(ok10)
    # 11. terminal states / nothing skipped
    ok11 = j["state"].isin(["COMPLETED_ON_TIME", "COMPLETED_LATE"]).all() and j["finish_time"].notna().all() \
        and ri["jobs_planned"] == ri["jobs_submitted"] == len(wl) and ri["failures_fired"] == ri["failures_scheduled"]
    agg["11"] &= bool(ok11)
    # FIFO, one job at a time per host stream, never before submission
    okf = (j["start_time"] >= j["submit_time"] - 1e-6).all() and (j["queue_delay_sec"] >= -1e-6).all()
    for s, g in j.sort_values(["stream", "job"]).groupby("stream"):
        okf &= bool((g["start_time"].values[1:] >= g["finish_time"].values[:-1] - 1e-6).all())
        okf &= bool((pd.Series(g["start_time"].values).is_monotonic_increasing))
    agg["fifo"] &= bool(okf)
    # accounting identity
    bound = 0.1 * (j["length_sec"] / 3600 * 3 + 40) + 1
    res = j["turnaround_sec"] - (j["queue_delay_sec"] + j["length_sec"] + j["checkpoint_overhead_sec"]
                                 + j["lost_work_sec"] + j["interrupted_write_sec"] + j["recovery_sec"])
    agg["id"] &= bool((res >= -0.5).all() and (res <= bound).all())
    resid_txt.append(f"{r}: {res.max():.2f}s")
    # checkpoints by tier (tier in force when the checkpointed segment started)
    for (failing, t), g in ck.assign(failing=ck["stream"].isin(fail_time)).groupby(["failing", "tier"]):
        ck_tier_rows.append({"run": r, "hosts": "failing" if failing else "non_failing", "tier": t,
                             "checkpoints": len(g), "overhead_h": len(g) * C / 3600})
    # summary
    failing = j["stream"].isin(fail_time)
    for scope, m in (("all", j.index == j.index), ("failing_hosts", failing), ("non_failing_hosts", ~failing)):
        x = j[m]
        summ.append({"run": r, "scope": scope, "streams": x["stream"].nunique(), "jobs": len(x),
                     "on_time": int((x["state"] == "COMPLETED_ON_TIME").sum()),
                     "late": int((x["state"] == "COMPLETED_LATE").sum()),
                     "on_time_pct": round(100 * x["success"].mean(), 3),
                     "useful_work_h": round(x["length_sec"].sum() / 3600, 1),
                     "checkpoints": int(x["checkpoints"].sum()),
                     "checkpoints_per_job_mean": round(x["checkpoints"].mean(), 3),
                     "checkpoint_overhead_h": round(x["checkpoint_overhead_sec"].sum() / 3600, 2),
                     "overhead_ratio_pct": round(100 * x["checkpoint_overhead_sec"].sum() / x["length_sec"].sum(), 3),
                     "failures": int(x["failures"].sum()), "lost_work_h": round(x["lost_work_sec"].sum() / 3600, 3),
                     "recovery_h": round(x["recovery_sec"].sum() / 3600, 4),
                     "queue_delay_mean_h": round(x["queue_delay_sec"].mean() / 3600, 3),
                     "queue_delay_max_h": round(x["queue_delay_sec"].max() / 3600, 2),
                     "turnaround_mean_h": round(x["turnaround_sec"].mean() / 3600, 3),
                     "turnaround_over_length_mean": round((x["turnaround_sec"] / x["length_sec"]).mean(), 4),
                     "last_finish_day": round(x["finish_time"].max() / DAY, 2)})

check("6_checkpoint_save_time_counted_as_overhead", agg["6"], "overhead = 300 s x completed checkpoints = log count")
check("7_restore_and_boot_time_included", agg["7"], "ready at +D+B (also for idle failures); restore done at +D+B+R")
check("8_lost_work_from_latest_completed_checkpoint", agg["8"], "committed = last checkpoint; lost = time since commit/start")
check("9_replacement_hosts_selected_and_used", agg["9"],
      "distinct spare per failure; interrupted + later jobs run on it; earlier jobs on primary; spares never fail")
check("10_deadline_recorded_correctly", agg["10"], "deadline = submit + 1.5 L; state/success consistent with finish")
check("11_every_submitted_job_reaches_terminal_state", agg["11"],
      "planned == submitted == finished for every run; states only COMPLETED_ON_TIME / COMPLETED_LATE")
check("fifo_one_job_at_a_time_never_before_submit", agg["fifo"], "start >= submit; start >= previous finish; FIFO order")
check("accounting_identity_turnaround", agg["id"],
      "turnaround = queue + L + overhead + lost + interrupted + recovery; max residual " + "; ".join(resid_txt))

# 12. labels
inputs = json.load(open(os.path.join(RUN1, "inputs.json")))
scr = os.path.join(PILOT, "check_labels_scrambled")
same_scr = True
for r in runs_in(scr):
    for fn in ("jobs.csv", "failure_events.csv", "recovery_events.csv", "hosts.csv"):
        same_scr &= open(os.path.join(RUN1, r, fn), "rb").read() == open(os.path.join(scr, r, fn), "rb").read()
    same_scr &= gzip.open(os.path.join(RUN1, r, "checkpoint_events.csv.gz")).read() == \
        gzip.open(os.path.join(scr, r, "checkpoint_events.csv.gz")).read()
check("12_no_prediction_labels_read",
      inputs["label_column_index"] == 4 and inputs["extracted_column_indices"] == "[0, 1, 6]" and same_scr,
      f"label column {inputs['label_column_index']} never extracted (extracted {inputs['extracted_column_indices']}); "
      f"outputs byte-identical with ~50% labels scrambled ({runs_in(scr)}): {same_scr}")

# determinism
diff = []
for root, _, files in os.walk(RUN1):
    for fn in files:
        if fn == "resources.csv":
            continue
        p1 = os.path.join(root, fn)
        p2 = os.path.join(RUN2, os.path.relpath(p1, RUN1))
        rd = (lambda p: gzip.open(p).read()) if fn.endswith(".gz") else (lambda p: open(p, "rb").read())
        if not os.path.exists(p2) or rd(p1) != rd(p2):
            diff.append(os.path.relpath(p1, RUN1))
nfiles = sum(len(f) for _, _, f in os.walk(RUN1)) - 1
check("determinism_run1_equals_run2", not diff, f"{nfiles} output files compared; differing: {diff}")

# distribution-shift reporting: tier occupancy over host-days 1..30 (days with any effective score)
occ = tl[tl["day"].between(1, 30)].copy()
occ["hosts"] = occ["stream"].map(lambda s: "failing" if s in fail_time else "non_failing")
occ_rows = []
for scope, g in (("all", occ), ("failing", occ[occ["hosts"] == "failing"]), ("non_failing", occ[occ["hosts"] == "non_failing"])):
    vc = g["tier"].value_counts(normalize=True)
    occ_rows.append({"hosts": scope, "host_days": len(g), **{t: round(100 * vc.get(t, 0), 3) for t in ("LOW", "MEDIUM", "HIGH")}})
occ_rows.append({"hosts": "validation_design_target", "host_days": None, "LOW": 90.0, "MEDIUM": 9.0, "HIGH": 1.0})
pd.DataFrame(occ_rows).to_csv(os.path.join(OUT, "tier_occupancy.csv"), index=False)
pd.DataFrame(ck_tier_rows).to_csv(os.path.join(OUT, "checkpoints_by_tier.csv"), index=False)
pd.DataFrame(summ).to_csv(os.path.join(OUT, "pilot_summary.csv"), index=False)
pd.DataFrame(per_fail).to_csv(os.path.join(OUT, "per_failure.csv"), index=False)
results["all_pass"] = all(v["pass"] for v in results.values() if isinstance(v, dict))
json.dump(results, open(os.path.join(OUT, "validation_results.json"), "w"), indent=2)
print("ALL PASS" if results["all_pass"] else "SOME CHECKS FAILED")
