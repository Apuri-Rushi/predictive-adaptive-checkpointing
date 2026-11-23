#!/usr/bin/env python
"""
Resumable driver for the full experiment: shards crc32(serial) % 56 == k, k = 0..55.

For each shard (in order) not yet marked DONE:
  * runs ExperimentRunner into <out>/shard_KK.tmp  (E1 + E2/E3 for every T0, identical inputs per shard)
  * on success: hashes every output file, writes <out>/shard_KK/OUTPUT_SHA256.txt and a DONE marker,
    renames .tmp -> final, appends a row to <out>/manifest.csv
  * on failure: keeps the log, records status FAILED in the manifest, continues with the next shard
Re-running the same command skips DONE shards (resume). A shard is never half-written: only complete
shards are renamed to their final name.

Usage (from project/cloudsim):
    python -I research/scripts/run_full.py --out results/full [--shards 56] [--only 0,1,2]
                                           [--utilization 1.0] [--t0 1,4,12,24,72] [--workers 2]
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
CLOUDSIM = os.path.dirname(RESEARCH)
PROJ = os.path.dirname(CLOUDSIM)
JAVA8 = r"C:\Program Files\Java\jre1.8.0_501\bin\java.exe"
CP = os.pathsep.join([os.path.join(CLOUDSIM, "vendor", "cloudsim-3.0.3", "jars", "cloudsim-3.0.3.jar"),
                      os.path.join(RESEARCH, "build", "classes")])
PRED = os.path.join(PROJ, "ml", "results", "model_evaluation", "test_predictions.csv.gz")
FAIL = os.path.join(PROJ, "ml", "results", "dataset_audit_revalidation", "drive_failure_summary.csv")
FIELDS = ["shard", "status", "started_utc", "finished_utc", "wall_seconds", "max_peak_heap_mb", "hosts",
          "planned_jobs", "failures", "workload_sha256", "failures_sha256", "outputs_sha256", "utilization",
          "t0_hours", "log"]


def sha_file(p):
    h = hashlib.sha256()
    opener = gzip.open if p.endswith(".gz") else open      # hash decompressed content (gzip header has mtime)
    with opener(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--shards", type=int, default=56)
    ap.add_argument("--only", default="")
    ap.add_argument("--utilization", default="1.0")
    ap.add_argument("--t0", default="1,4,12,24,72")
    ap.add_argument("--hosts-per-dc", default="50")
    ap.add_argument("--workers", type=int, default=1, help="shards run in parallel (separate JVMs)")
    ap.add_argument("--xmx", default="1200m")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    manifest = os.path.join(a.out, "manifest.csv")
    if not os.path.exists(manifest):
        with open(manifest, "w", newline="") as f:
            csv.writer(f).writerow(FIELDS)
    config = {"shards": a.shards, "utilization": a.utilization, "t0": a.t0, "hosts_per_dc": a.hosts_per_dc,
              "predictions": PRED, "failures": FAIL, "java": JAVA8, "classpath": CP}
    cfg_path = os.path.join(a.out, "run_config.json")
    if os.path.exists(cfg_path):
        old = json.load(open(cfg_path))
        if {k: old.get(k) for k in ("shards", "utilization", "t0", "hosts_per_dc")} != \
                {k: config[k] for k in ("shards", "utilization", "t0", "hosts_per_dc")}:
            sys.exit(f"configuration differs from the existing run in {a.out}; refusing to mix results")
    else:
        json.dump(config, open(cfg_path, "w"), indent=2)

    todo = [int(x) for x in a.only.split(",")] if a.only else list(range(a.shards))
    lock = threading.Lock()

    def run_shard(k):
        final = os.path.join(a.out, f"shard_{k:02d}")
        if os.path.exists(os.path.join(final, "DONE")):
            print(f"shard {k:02d}: DONE - skipped", flush=True)
            return
        tmp = final + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        log = os.path.join(a.out, f"shard_{k:02d}.log")
        start = time.time()
        started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        cmd = [JAVA8, f"-Xmx{a.xmx}", "-cp", CP, "ckpt.ExperimentRunner", "--predictions", PRED, "--failures", FAIL,
               "--out", tmp, "--shard", str(k), "--shards", str(a.shards), "--t0", a.t0,
               "--hosts-per-dc", a.hosts_per_dc, "--utilization", a.utilization]
        with open(log, "w") as lf:
            rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT)
        row = {"shard": k, "started_utc": started,
               "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "wall_seconds": round(time.time() - start, 1), "utilization": a.utilization, "t0_hours": a.t0,
               "log": os.path.basename(log)}
        if rc == 0:
            inp = json.load(open(os.path.join(tmp, "inputs.json")))
            peaks = [int(l.split(",")[2]) for l in open(os.path.join(tmp, "resources.csv")).read().splitlines()[1:]]
            hashes = []
            for root, _, files in sorted(os.walk(tmp)):
                for fn in sorted(files):
                    if fn == "resources.csv":
                        continue
                    pth = os.path.join(root, fn)
                    hashes.append(f"{sha_file(pth)}  {os.path.relpath(pth, tmp)}")
            open(os.path.join(tmp, "OUTPUT_SHA256.txt"), "w").write("\n".join(hashes) + "\n")
            row.update({"status": "DONE", "max_peak_heap_mb": max(peaks), "hosts": inp["hosts"],
                        "planned_jobs": inp["planned_jobs"], "failures": inp["failures_loaded"],
                        "workload_sha256": inp["workload_sha256"], "failures_sha256": inp["failures_sha256"],
                        "outputs_sha256": hashlib.sha256("\n".join(hashes).encode()).hexdigest()})
            open(os.path.join(tmp, "DONE"), "w").write(row["finished_utc"] + "\n")
            shutil.rmtree(final, ignore_errors=True)
            os.rename(tmp, final)
        else:
            row["status"] = f"FAILED(rc={rc})"
        with lock:                                   # manifest written by one thread at a time
            with open(manifest, "a", newline="") as f:
                csv.DictWriter(f, FIELDS).writerow(row)
            print(f"shard {k:02d}: {row['status']} in {row['wall_seconds']} s", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for fut in [ex.submit(run_shard, k) for k in todo]:
            fut.result()

if __name__ == "__main__":
    main()
