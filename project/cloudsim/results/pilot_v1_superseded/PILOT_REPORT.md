# Pilot Report — Trace-Driven CloudSim Pilot, Shard 0 of 56

**Status: the pilot PASSED all 16 validation checks and is ready for review. The full 56-shard experiment has NOT been started.**

| Item | Value |
|---|---|
| Simulator | CloudSim 3.0.3 (official jar), research code in `project/cloudsim/research/` |
| Java | compiled with JDK 24 `javac --release 8`, run on Java 1.8.0_501 (`-Xmx1500m`) |
| Shard | `crc32(serial_number) % 56 == 0` → **1,984 hosts** (drives) |
| Inputs (read-only) | `project/ml/results/model_evaluation/test_predictions.csv.gz`, `project/ml/results/dataset_audit_revalidation/drive_failure_summary.csv` |
| Configuration | Unchanged from approval: tiers < 0.000234 / < 0.001732 / ≥ 0.001732; intervals 2.65 T₀ / T₀ / T₀ ÷ 4.9; C = R = 300 s; D = 60 s; B = 120 s; jobs 24 / 72 / 168 h (p = 0.5 / 0.3 / 0.2); deadline 1.5 L; T₀ ∈ {1, 4, 12, 24, 72} h; 50 hosts per datacenter entity; no new job after 2019-07-01 00:00, running jobs drain |
| Runs | E1 + 5 × E2 + 5 × E3 = 11 policy runs, executed **twice** (`run1/`, `run2/`), plus 2 diagnostic runs (`check_labels_scrambled/`, `check_no_failures/`) |

## Commands

From `project/cloudsim/`:

```
bash research/scripts/build_and_test.sh                         # build + 65 scenario checks (all pass)
bash research/scripts/run_pilot.sh results/pilot/run1
bash research/scripts/run_pilot.sh results/pilot/run2
PRED=<scratch copy with label_primary scrambled> bash research/scripts/run_pilot.sh results/pilot/check_labels_scrambled --t0 4
bash research/scripts/run_pilot.sh results/pilot/check_no_failures --t0 4 --no-failures
python -I research/validation/validate_pilot.py results/pilot
```

The scrambled copy is a scratch file outside the project. It changed 1,273,481 of 2,544,754 labels; the original prediction file was not modified.

## 1. Validation results (`validation/validation_results.json`)

These are **independent** checks: Python recomputes the expected values from the raw input files without using the Java code.

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 1 | All input hosts loaded correctly | **PASS** | The 1,984 serials match an independent recomputation of the shard. All 45,523 score rows and each host's first day match |
| 2 | Prediction timestamps applied without look-ahead | **PASS** | 75,392 host-days: the score in force at 00:00 of day d is the latest score dated ≤ d − 1. 0 mismatches; 0 cases of a same-day or future score being used |
| 3 | Missing predictions use only the last available score | **PASS** | 27,816 host-days are served by carry-forward; 0 tier mismatches |
| 4 | Actual failure dates read only by the failure injector | **PASS** | (a) The injector's 3 events match an independent recomputation: (stream 1468, t = 322,061 s), (906, 963,029 s), (1637, 1,612,909 s).<br>(b) The broker and policy source code never reference failure data.<br>(c) Running E3 with and without the failure trace gives **identical decisions before the first failure**. After a failure, other hosts show only timing jitter of ≤ 0.22 s, confined to the 4 datacenter entities holding a failed host or an active spare. The cause: CloudSim updates progress for a whole datacenter at once, so the extra cancel/recovery events shift neighbouring completion times slightly. Never-failing hosts keep identical tiers and identical checkpoint counts per job |
| 5 | Same failure events and workloads for all policies | **PASS** | All 22 policy runs share one hash for workload, failures and tier timeline. The job mix was regenerated independently from `crc32` |
| 6 | Checkpoint save time counted as overhead | **PASS** | For every job, overhead = 300 s × completed checkpoints, and equals the checkpoint event log. E1 has 0 checkpoints |
| 7 | Restore and replacement boot time included | **PASS** | The replacement is ready exactly D + B = 180 s after a failure; the restore finishes at +480 s when a checkpoint exists. `recovery_sec` per job matches |
| 8 | Lost computation from the latest completed checkpoint | **PASS** | For each of the 33 failure records, committed work = the last committed checkpoint before the failure, and lost = progress − committed = time since that checkpoint (or the job start) |
| 9 | Replacement hosts selected and used correctly | **PASS** | Each failure gets a distinct spare (hosts 1984, 1985, 1986). The job continues there and later jobs stay there. Spares are never marked failed; exactly the 3 failed primaries are |
| 10 | Deadline success/failure correctly recorded | **PASS** | `success` = finish ≤ submit + 1.5 L for every job in every run |
| 11 | Every started job reaches a terminal state | **PASS** | All jobs finish (the runner also stops on any stalled job). Failures fired = scheduled. No stream used up its 40-job list |
| 12 | No ML prediction labels read | **PASS** | Header column 4 (`label_primary`) is never extracted; the loader cuts out only columns [0, 1, 6]. With about 50 % of labels scrambled, all outputs of E1, E2 (T₀ = 4 h) and E3 (T₀ = 4 h) are **byte-identical** |
| — | Time accounting identity | **PASS** | turnaround = L + overhead + lost + interrupted writes + recovery, within ≤ 1.63 s per job (CloudSim's 0.1 s event granularity per cloudlet) |
| — | **Determinism** | **PASS** | All 70 output files of `run1` and `run2` are byte-identical (`resources.csv`, which holds wall time and memory, excluded) |

**Two checks failed on the first validation pass. Both were problems with the checks, not the simulator, and both were investigated before the check was changed:**
* **Check 11** compared CSV times rounded to 3 decimals against the horizon. One job started at 2,591,999.9997 s, which printed as 2,592,000.000. A 0.001 s rounding tolerance was added.
* **Check 4c** first demanded byte-identical histories after other hosts' failures. The differences turned out to be ≤ 0.22 s timing jitter inside the affected datacenter entities, starting only after a failure there, with no change to any tier or checkpoint count. The check now tests exactly those properties.

## 2. Pilot results (`validation/pilot_summary.csv`) — functional only, NOT research conclusions

The shard contains **only 3 failures**, so the benefit side (lost work avoided) rests on 3 events. Do not draw conclusions from these numbers.

**All hosts** (1,984 streams). The overhead and wasted columns are % of useful work.

| Policy | Jobs | Success % | Checkpoints per job | Overhead % | Lost work (h) | Recovery (h) | Wasted % |
|---|---|---|---|---|---|---|---|
| E1 no checkpointing | 22,480 | 99.996 | 0 | 0 | 133.0 | 0.15 | 0.009 |
| E2 fixed, T₀ = 1 h | 21,083 | 100 | 66.4 | 8.21 | 1.8 | 0.40 | 8.21 |
| E3 adaptive, T₀ = 1 h | 21,454 | 100 | 58.2 | 7.20 | 0.3 | 0.40 | 7.20 |
| E2 fixed, T₀ = 4 h | 22,484 | 100 | 15.9 | 1.96 | 9.4 | 0.40 | 1.96 |
| E3 adaptive, T₀ = 4 h | 22,391 | 100 | 14.7 | 1.81 | 0.7 | 0.40 | 1.81 |
| E2 fixed, T₀ = 12 h | 22,484 | 100 | 4.6 | 0.57 | 8.2 | 0.40 | 0.57 |
| E3 adaptive, T₀ = 12 h | 22,484 | 100 | 4.4 | 0.55 | 3.7 | 0.40 | 0.55 |
| E2 fixed, T₀ = 24 h | 22,484 | 99.996 | 1.8 | 0.22 | 35.0 | 0.32 | 0.23 |
| E3 adaptive, T₀ = 24 h | 22,484 | 100 | 1.9 | 0.24 | 4.8 | 0.40 | 0.24 |
| E2 fixed, T₀ = 72 h | 22,483 | 99.996 | 0.4 | 0.05 | 60.4 | 0.23 | 0.05 |
| E3 adaptive, T₀ = 72 h | 22,485 | 100 | 0.4 | 0.05 | 11.9 | 0.40 | 0.05 |

**The 3 failing hosts** (`per_failure.csv` gives each failure):

| | E1 | E2, 4 h | E3, 4 h | E2, 24 h | E3, 24 h |
|---|---|---|---|---|---|
| Lost work (h) | 133.0 | 9.4 | 0.7 | 35.0 | 4.8 |

* All 3 failing drives were in the **HIGH tier when they failed**. One (ZCH07BDG) was HIGH from 2 days before its failure day; the other two were HIGH for at least 4 days. So E3 was checkpointing at T₀ / 4.9 when the failures came.
* E1 has one deadline miss: stream 1468's 24 h job took 41.5 h because it restarted from zero.

## 3. Runtime and memory (`run1/resources.csv`)

| | |
|---|---|
| Trace loading | 17.9 s, once per invocation; scans all 2.54 M prediction rows |
| Wall time per policy run | 0.6 s (E1) · 1–9 s (T₀ = 4–72 h) · 33–34 s (T₀ = 1 h) |
| Full 11-run pilot | ≈ 2 min |
| Peak Java heap per run | 114–197 MB in `run1` (up to ~520 MB observed in the diagnostic runs; limit 1,500 MB) |
| Largest run | 2.88 M cloudlets (E2, T₀ = 1 h) |
| Output size | ~77 MB per shard for all 11 runs with full event logs |

**Projection for 56 shards:** about 2 hours of compute and about 4.3 GB of output with full checkpoint logs.

## 4. Output layout

```
results/pilot/
├── run1/, run2/                      # identical repeats
│   ├── inputs.json                   # shard, counts, label-column index, extracted columns, input hashes
│   ├── streams.csv                   # per host: serial, first day, start time, score count, 40 job lengths
│   ├── tier_timeline.csv             # per host and day: score in force at 00:00 and its tier
│   ├── injector_failures.csv         # the failure events given to the injector (audit copy)
│   ├── resources.csv                 # wall time, peak heap, cloudlets per run
│   └── <policy>/                     # E1_none, E2_fixed_T0_{1,4,12,24,72}h, E3_adaptive_T0_{...}h
│       ├── jobs.csv                  # per job: L, submit, finish, deadline, success, checkpoints, overhead, lost, recovery, hosts used
│       ├── hosts.csv                 # per host: failure flag and time, jobs, totals (+ spare-host failed flags)
│       ├── checkpoint_events.csv.gz  # every completed checkpoint
│       ├── failure_events.csv        # phase, progress, committed, lost, failed host -> replacement host
│       ├── recovery_events.csv       # replacement ready (+D+B), restore completed (+R)
│       └── run_info.json             # policy, hashes, failures scheduled/fired/applied, cloudlets
├── check_labels_scrambled/, check_no_failures/   # diagnostic runs for checks 12 and 4c
└── validation/                       # validation_results.json, pilot_summary.csv, per_failure.csv
```

## 5. Limitations and points for review (no settings were changed)

1. **June tier occupancy differs strongly from the validation design target.** Across host-days 1–30 the shard is **53.8 % LOW, 39.6 % MEDIUM and 6.7 % HIGH**, against the 90 / 9 / 1 % the thresholds produced on validation. This matches the score shift Phase 2 reported for June (mean corrected score 0.046 % vs 0.019 % on validation). The adaptive policy therefore checkpoints many never-failing hosts at the MEDIUM or HIGH rate. As instructed, thresholds were **not** changed; this needs to be discussed with the full results.
2. **The job set is not identical across policies.** Heavier checkpointing slows streams, so fewer jobs start before the horizon (21,083 at fixed T₀ = 1 h vs 22,484 at T₀ = 4 h). Ratios per unit of useful work are comparable, but absolute totals are not. **Decision needed before the full run:** keep the approved horizon rule as is, or fix the job set per stream (e.g. the jobs that start under E1) and run all of them to completion in every policy.
3. **CloudSim datacenter-level coupling:** after a failure, neighbouring hosts in the same 50-host datacenter entity shift by ≤ 0.22 s (check 4c). This does not affect decisions or counts. It is a small simulator artefact, well below the minute- and hour-scale quantities being compared.
4. **3 failures in the pilot.** All benefit-side numbers are anecdotal until all 56 shards (≈ 175 failures) are run.
5. Failure time within the day is a deterministic hash-based offset, as designed. The sensitivity offsets (0 and 86,399 s) were not part of the pilot.
6. The disk-to-host abstraction, the spare hosts that never fail, and hosts leaving without failure staying up are all approved assumptions, applied unchanged.

## 6. Code added in this stage (`project/cloudsim/research/`)

| Area | Files |
|---|---|
| Trace input | `src/ckpt/trace/RiskTraceLoader.java` (extracts columns by position, never the label), `FailureTraceLoader.java`, `WorkloadGenerator.java`, `Hashing.java` |
| Logging | `src/ckpt/sim/EventLog.java` (checkpoint, failure and recovery logs); hooks added to `CheckpointingBroker` |
| Runner | `src/ckpt/ExperimentRunner.java` (one shard, all policies, audit files and hashes) |
| Scripts | `scripts/run_pilot.sh`, `validation/validate_pilot.py` (independent checks) |

The scenario test suite still passes 65 / 65 checks after these changes.
