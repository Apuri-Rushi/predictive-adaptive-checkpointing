# CloudSim 3.0.3 Setup Log and Pilot Architecture

**Phase 3, stage 1: baseline CloudSim setup and the checkpoint / failure / recovery mechanism.**
The ML dataset, pipeline, model and predictions were not touched. No trace data has been loaded into CloudSim yet.

---

## 1. Download and verification

| Item | Value |
|---|---|
| Source | Official release `cloudsim-3.0.3` of `github.com/Cloudslab/cloudsim` (published 2015-03-19) |
| Assets | `cloudsim-3.0.3.zip` (13,687,140 B) and `cloudsim-3.0.3.tar.gz` (10,379,100 B); sizes match the GitHub API listing |
| SHA-256 | zip `966322187fc5eda7088279213bc3b2c3f5edc1adef0734b4457859348689d2fd`<br>tar.gz `4467a4b77f1afa094cc60615078eaaace04e6e041ea2d6059c23a77b7ae6ad68`<br>(saved in `vendor/downloads/SHA256SUMS.txt`) |
| Integrity | GitHub publishes no checksums. Verified instead by:<br>• ZIP CRC test passes;<br>• the tar.gz opens;<br>• all 12,293 files are byte-identical between zip and tar.gz (the zip only adds 5 directory entries);<br>• the extracted tree matches the zip byte for byte, with 0 extra files |
| Archives kept | `vendor/downloads/` (original archives, unmodified) |
| Extracted to | `vendor/cloudsim-3.0.3/`, **unmodified**: `license.txt`, `readme.txt`, `release_notes.txt`, `changelog.txt`, `docs/` (Javadoc), `sources/`, `examples/`, `jars/`, `build.xml`, `pom.xml` |

## 2. Dependencies

| Jar | Shipped | Needed by this project |
|---|---|---|
| `jars/cloudsim-3.0.3.jar` | yes | **yes**: the only runtime dependency |
| `jars/cloudsim-examples-3.0.3.jar` | yes | only for the official examples |
| `jars/*-sources.jar` | yes | no (reference) |
| Apache Commons Math 3 (`org.apache.commons.math3`) | **no** | **no.** Imported only by `util/MathUtil` and `power/PowerVmSelectionPolicyMaximumCorrelation`, which belong to the power-aware package. The research code never loads them, so it was not downloaded |

The bundled `pom.xml` is a stale toolkit-2.1 file that lists no dependencies. The facts above come from the source imports.

## 3. Java toolchain (no system setting changed)

| Tool | Path | Version |
|---|---|---|
| Compiler | `C:\Program Files\Java\jdk-24\bin\javac.exe` | javac 24.0.2, used with **`--release 8`** (Java 8 API and class-file format) |
| Runtime | `C:\Program Files\Java\jre1.8.0_501\bin\java.exe` | **java 1.8.0_501** (HotSpot 25.501-b08) |

The Java 8 installation is a JRE only (no `javac`). That is why JDK 24 compiles with `--release 8`, which gives the Java 8 API and bytecode. Everything **runs** on Java 8. Both tools are called by absolute path; `PATH` and `JAVA_HOME` were not changed.

## 4. Commands and results

All commands are run from `project/cloudsim/`, with:
`CS=C:/Users/rushi/CC_project/project/cloudsim/vendor/cloudsim-3.0.3/jars/cloudsim-3.0.3.jar`

**4.1 Official example from the prebuilt jar on Java 8**
```
"C:/Program Files/Java/jre1.8.0_501/bin/java.exe" -cp "$CS;vendor/cloudsim-3.0.3/jars/cloudsim-examples-3.0.3.jar" org.cloudbus.cloudsim.examples.CloudSimExample1
```
Result: Cloudlet 0 SUCCESS, start 0.1, finish 400.1.

**4.2 Official example compiled from source, run on Java 8**
```
"C:/Program Files/Java/jdk-24/bin/javac.exe" --release 8 -d build/examples -cp "$CS" vendor/cloudsim-3.0.3/examples/org/cloudbus/cloudsim/examples/CloudSimExample1.java
"C:/Program Files/Java/jre1.8.0_501/bin/java.exe" -cp "$CS;build/examples" org.cloudbus.cloudsim.examples.CloudSimExample1
```
Result: identical (SUCCESS, 400.1).

**4.3 Minimal datacenter** (`research/src/ckpt/app/MinimalDatacenter.java`, stock CloudSim classes only)

Setup: 1 datacenter, 2 hosts (1 PE, 1000 MIPS), 2 VMs, 4 space-shared cloudlets.

| Cloudlet | VM | Start | Finish | Status |
|---|---|---|---|---|
| 1 | 1 | 0.10 | 200.10 | SUCCESS |
| 3 | 1 | 200.10 | 300.10 | SUCCESS |
| 0 | 0 | 0.10 | 400.10 | SUCCESS |
| 2 | 0 | 400.10 | 700.10 | SUCCESS |

4/4 completed at exactly the expected times.

**4.4 Research build and scenario tests**
```
bash research/scripts/build_and_test.sh
```
This compiles `research/src` and `research/test` with `javac --release 8 -Xlint:all` (no warnings), then runs `MinimalDatacenter` and `ckpt.ScenarioTests` on Java 8.

## 5. Scenario test results: **65 / 65 checks passed**

Parameters (approved): C = R = 300 s, D = 60 s, B = 120 s, deadline = 1.5 L, 1000 MIPS, job L = 24 h, fixed T₀ = 4 h.

**Required scenarios** (expected values are hand-calculated):

| Scenario | Setup | Expected (hand-computed) | Simulated | Result |
|---|---|---|---|---|
| **S1 Normal completion** | No failure | 5 checkpoints; finish = L + 5C = 87,900 s; deadline met | 5; 87,900.1 s; met | PASS |
| **S2 Checkpoint followed by failure** | Failure at 10 h | Checkpoints committed at 14,400 and 28,800 s of work; lost = 36,000 − 29,400 = 6,600 s | Committed 28,800; lost 6,599.9 s | PASS |
| **S3 Recovery from latest checkpoint** | Same run | Restore done at 36,000 + D + B + R = 36,480; recovery 480 s; finish 94,980 s; 5 checkpoints | 36,480.0; 480; 94,980.0; 5 | PASS |
| **S4 Resume on replacement host** | Same run | Hosts used [0 → 1]; host 0 failed, host 1 not; restore on VM 1 | As expected | PASS |
| **S5 Failure before first checkpoint** | Failure at 2 h | Lost 7,200 s; recovery D + B = 180 s (nothing to restore); restart from zero; finish 95,280 s | 7,199.9; 180; 95,280.0 | PASS |
| **S6 Deadline miss** | No checkpointing; failure at 23 h | Finish 82,800 + 180 + 86,400 = 169,380 > deadline 129,600 → not successful | 169,380.0; success = false | PASS |

**Additional checks:**

| ID | What it tests | Result |
|---|---|---|
| X1 | Failure **during a checkpoint write** (t = 14,550 s): the write is lost (149.9 s), lost work is 14,400 s, restart from zero | PASS |
| X2 | Adaptive tiers with T₀ = 4 h: HIGH gives 29 checkpoints (T = 2,938.8 s); LOW gives 2 (T = 38,160 s); MEDIUM gives 5 (same as fixed); none gives 0 | PASS |
| X3 | The day-d score applies from 00:00 on day d+1; missing days carry the last score forward; MEDIUM before any score; boundaries 0.000234 → MEDIUM and 0.001732 → HIGH | PASS |
| X4 | LOW → HIGH tier change at midnight: the overdue checkpoint is taken immediately (86,700 s), then checkpoints every 3,238.8 s (T + C) | PASS |
| X5 | 3 streams in 3 datacenters, 2 failures: each moves to its own spare; the unaffected stream is unchanged | PASS |

The small offsets (≤ 0.1 s) come from CloudSim's start-up time (0.1 s) and its event granularity.

## 6. Compatibility issues found in CloudSim 3.0.3, and how they are handled

| # | Issue (confirmed by reading `sources/`) | Handling |
|---|---|---|
| 1 | `CloudletSchedulerSpaceShared.cloudletPause()` does not release the PE (`usedPes` is not decremented), so a later resume on a 1-PE VM goes to the waiting queue for good | **Pause/resume is not used.** Checkpoints are separate C-second cloudlets between compute segments (the design's fallback, §7) |
| 2 | `cloudletResume()` sets the cloudlet's length to its *remaining* length while keeping the work done so far, so that work is counted twice. `Datacenter.processCloudletResume()` also passes an absolute time to `schedule()`, which expects a delay | Same as #1 |
| 3 | `processCloudletPause` and `processCloudletCancel` do not update progress first, so the cloudlet's "finished so far" value is stale | Progress at a failure is computed exactly from the segment start time (a dedicated 1-PE VM runs at a constant rate). Cancel is used only on failed hosts, which are never reused |
| 4 | A cloudlet that finishes within `minTimeBetweenEvents` (0.1 s) of the last update can **stall silently**, because `updateCloudletProcessing` skips the update | Segments shorter than 1 s are never created; a remainder under 1 s is merged. `SimulationRunner` now **fails loudly** if any started job never finishes. This bug was found by test X2 |
| 5 | `CloudSim.runClockTick()` loops over **all entities** on every event, and `Datacenter.updateCloudletProcessing()` loops over all hosts in that datacenter | Hosts are grouped 50 per datacenter, and the simulation is split into shards of about 2,000 hosts (§7) |
| 6 | The stock `DatacenterBroker` destroys VMs at the end, so `vm.getHost()` is null afterwards | The research broker records hosts used per job during the run |
| 7 | No `javac` for Java 8 is installed | JDK 24 `javac --release 8`; runs on the Java 8 JRE |
| 8 | No host-failure injection, checkpointing or recovery built in (as expected in the design, §1.2) | Custom `FailureInjector` and `CheckpointingBroker` |

## 7. Scale benchmark (synthetic streams, no trace data)

Settings: 30-day horizon, approved job mix, fixed T₀ = 1 h (the densest checkpointing in the sweep), about 0.16 % of hosts failing.

| Streams | Hosts per datacenter | Cloudlets | Wall time | Heap used |
|---|---|---|---|---|
| 500 | 50 | 0.72 M | 1.5 s | ~44 MB |
| 500 | 500 | 0.72 M | 5.1 s | ~49 MB |
| 2,000 | 50 | 2.88 M | **15.0 s** | ~36 MB |
| 2,000 | 20 | 2.88 M | 19.5 s | ~45 MB |
| 14,000 | 50 | 20.2 M | **867.6 s** | ~163 MB |

* Runtime grows **faster than linearly** with shard size because of issue #5. Two thousand-host shards are about 8 times cheaper per host than 14,000-host shards.
* **Revised sharding:** K ≈ 56 shards of about 2,000 hosts (`crc32(serial) % 56`), instead of the design's K = 8.
* At the densest setting a 2,000-host run takes about 15 s. The full sweep (E1 + 5 × E2 + 5 × E3) over 56 shards should take under 3 hours, with low memory use.

## 8. Project structure

```
project/cloudsim/
├── ADAPTIVE_CHECKPOINTING_DESIGN.md      # Phase-3 design
├── SETUP_LOG.md                          # this file
├── vendor/                               # third-party, UNMODIFIED
│   ├── downloads/                        # original archives + SHA256SUMS.txt
│   └── cloudsim-3.0.3/                   # extracted official release
├── build/examples/                       # official CloudSimExample1 compiled from source
└── research/                             # custom research code (separate from CloudSim)
    ├── scripts/build_and_test.sh
    ├── src/ckpt/
    │   ├── app/      MinimalDatacenter, ScaleBenchmark
    │   ├── policy/   RiskTier, RiskTierClassifier, CheckpointPolicy, Policies (E1/E2/E3)
    │   ├── risk/     RiskSource, ConstantRisk, DailyScoreTimeline
    │   └── sim/      SimParams, StreamSpec, FailureEvent, JobRecord, CkptTags,
    │                 IdMappedVmAllocationPolicy, FailureInjector, CheckpointingBroker, SimulationRunner
    ├── test/ckpt/ScenarioTests.java
    └── build/classes/                    # compiled output
```

## 9. Pilot architecture (for review; NOT yet implemented or run)

**Goal:** run the trace-driven experiment on **one shard**: `crc32(serial) % 56 == 0`, about 2,000 drives. This checks loading, determinism, metrics and runtime before the full population. With about 3 failures expected in one shard, **pilot numbers are functional checks, not research results.**

### 9.1 New components

| Class | Responsibility | Leakage guard |
|---|---|---|
| `trace.RiskTraceLoader` | Streams `project/ml/results/model_evaluation/test_predictions.csv.gz` (GZIP, read-only). Keeps `serial_number`, `date` and `p_failure_7d_corrected` for serials in the shard. Builds one `DailyScoreTimeline` per drive (day index = date − 2019-06-01) | **Skips `label_primary` by column index**, so labels never enter the simulator. Asserts the header names |
| `trace.FailureTraceLoader` | Reads `project/ml/results/dataset_audit_revalidation/drive_failure_summary.csv`. Keeps drives in the shard **and** in the prediction pool with a June failure date. `t_fail = day × 86,400 + crc32("fail\|" + serial) mod 86,400` | Output goes **only** to `FailureInjector` |
| `trace.HostPool` | Pool = serials in the prediction file (110,848), sorted; shard selection; stream start = 00:00 of the drive's first prediction date | — |
| `workload.WorkloadGenerator` | 40 jobs per stream, lengths from `crc32(serial\|j) % 10`: 0–4 → 24 h, 5–7 → 72 h, 8–9 → 168 h (probabilities 0.5 / 0.3 / 0.2). Identical for every policy | — |
| `ExperimentRunner` (main) | Arguments: shard index, K, T₀ list. Runs E1, then E2(T₀) and E3(T₀) for T₀ ∈ {1, 4, 12, 24, 72} h, on identical streams and failures. Spares = shard failures + 1. Horizon: no new job starts after 2019-07-01 00:00; running jobs drain | Prints a hash of the workload and failure list per run, to prove the inputs are identical |
| `metrics.ResultsWriter` | Per-job CSV: policy, T₀, shard, stream, serial, job, L, submit, finish, deadline, success, checkpoints, overhead, lost work, recovery, failures, hosts used. Plus a summary JSON per policy, split into all / failing-host / non-failing-host streams | — |
| `metrics.TierOccupancy` | Daily tier shares in the shard vs the validation target (90 / 9 / 1 %); the tier of each failing host in the 24 h before its failure | Diagnostic only; never fed back to the policy |

### 9.2 Pilot acceptance checks (before any full run)

1. Loaded drives, scores per drive and shard failure count match counts computed independently in Python.
2. No `label_primary` value is read: the loader asserts it skipped that column.
3. Identical workload and failure hashes across E1, E2 and E3.
4. Every started job finishes. Failures fired = failures scheduled.
5. Per-job identity: Σ(turnaround) = Σ(L + overhead + lost + recovery), within the event-granularity tolerance. **No-failure jobs** under E2 and E3 match the analytical checkpoint count.
6. Runtime and memory per run recorded; the full-run estimate updated.

### 9.3 Open points for review

* The revised shard count (K = 56 instead of 8) follows from the benchmark.
* The pilot shard holds only about 3 of the 175 failures. A second check could run the shards containing failures first, but **every shard is still needed** for unbiased totals.
* The horizon and drain rule: no new jobs after 30 June; running jobs finish, even past the end of the trace scores. Carry-forward keeps the 23 June score in force.
