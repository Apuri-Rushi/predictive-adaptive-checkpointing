# Pilot Report (v2) — Common Predetermined Workload, Shard 0 of 56

**Status: the corrected workload mechanism is implemented and PASSES all checks: 90 / 90 scenario checks and 19 / 19 independent pilot checks, with byte-identical repeats. The full 56-shard experiment has NOT been launched. One decision is needed first (§4).**

The previous pilot (job set varied by policy) is kept for the record in `results/pilot_v1_superseded/`.

## 1. What changed

| Requirement | Implementation |
|---|---|
| Workload generated once, before any policy | `ExperimentRunner` builds the job plan once per shard (`WorkloadGenerator.plan`), writes `workload.csv`, hashes it, and passes the **same object** to every policy run. No policy generates jobs |
| Identical job IDs, lengths, submit times, host assignment | Job `"<serial>#<j>"`; length from the approved mix (`crc32(serial\|j) % 10` → 24 / 72 / 168 h, p = 0.5 / 0.3 / 0.2); assigned host = the drive's primary host |
| Predetermined submission times | Nominal back-to-back: `submit₀ = 00:00 of the host's first day`, `submitⱼ₊₁ = submitⱼ + Lⱼ`, generated while `submit < 30-day cutoff`. These are the arrival times if each job ran with no overhead and no failure |
| Queueing | A job arriving while its host is busy waits in that host's **FIFO queue** (one job at a time). Queueing delay = start − submit |
| After the cutoff | No submissions; every submitted job runs until it finishes (drain) |
| Deadline | submit + 1.5 L (unchanged). Turnaround = finish − submit, which includes queueing |
| Terminal states | `COMPLETED_ON_TIME` or `COMPLETED_LATE` (deadline missed). The runner stops with an error if any planned job is not submitted or any submitted job does not finish, so **no job can be skipped silently** |
| Failure while idle | No work lost; the stream moves to a spare host, which is ready after D + B. Jobs arriving meanwhile wait |

All approved settings are unchanged: model and predictions, thresholds 0.000234 / 0.001732, multipliers 2.65 / 1 / ÷4.9, C = R = 300 s, D = 60 s, B = 120 s, job mix, 1.5 L deadline, failure dates and offsets, spare-host rules, prediction timing and carry-forward.

## 2. Validation

### 2.1 Scenario tests: 90 / 90 passed

All 65 earlier checks still pass, plus 25 new ones:

| Test | What it confirms |
|---|---|
| W1 | Queueing behind checkpoint overhead: job 1 waits 1,500 s, finishes at 175,800 s, deadline met |
| W2 | Deadline miss caused by queueing behind a failure-delayed job (both jobs `COMPLETED_LATE`, neither skipped) |
| W3 | Failure while idle: no loss; the next job runs on the spare |
| W4 | A job arrives while the replacement is still booting and waits exactly 130 s |
| W5 | E1, E2 and E3 process identical job IDs, lengths, submit times and assigned hosts, and every job reaches a terminal state |

### 2.2 Pilot shard: 19 / 19 independent checks passed (`validation/validation_results.json`)

| Check | Result |
|---|---|
| 1 Hosts loaded (1,984; 45,523 scores) | PASS |
| 2 No look-ahead (75,392 host-days) | PASS |
| 3 Carry-forward only (27,816 host-days) | PASS |
| 4a–c Failure dates only via the injector | PASS. Before the first failure, the runs with and without failures are identical. Afterwards only ≤ 0.22 s timing jitter appears, inside the datacenter entities that hold a failed host or an active spare |
| **5a** Workload plan = independent Python regeneration (22,484 jobs: ids, lengths, submit times) | **PASS** |
| **5b** Every policy run (11 × 2) processed exactly the 22,484 planned jobs with identical stream/host, length and submit time; one input hash | **PASS** |
| 6 Checkpoint time counted as overhead | PASS |
| 7 Restore and boot included (including idle failures) | PASS |
| 8 Lost work from the latest completed checkpoint | PASS |
| 9 Replacement hosts (interrupted and later jobs on the spare; earlier jobs on the primary) | PASS |
| 10 Deadline = submit + 1.5 L; state consistent with finish time | PASS |
| **11** Planned = submitted = finished in every run; only terminal states | **PASS** |
| **FIFO** start ≥ submit, start ≥ previous finish, FIFO order | **PASS** |
| Accounting: turnaround = queue + L + overhead + lost + interrupted write + recovery | PASS (residual ≤ 1.6 s) |
| 12 No labels read (byte-identical outputs with ~50 % of labels scrambled) | PASS |
| Determinism: run1 = run2 (71 files) | PASS |

### 2.3 Full-run driver (`research/scripts/run_full.py`) — prepared, tested on shard 0 only

* **Resumable:** each shard runs in `shard_KK.tmp` and is renamed only when complete, with a `DONE` marker and `OUTPUT_SHA256.txt`. Re-running skips finished shards; a failed shard is recorded and the run continues.
* **Safe:** it refuses to continue in a folder created with a different configuration.
* **Manifest:** `manifest.csv` records status, start and end time, wall time, peak heap, hosts, jobs, failures, input hashes and output hash per shard.
* **Tested:** on shard 0 it ran (306.6 s, peak heap 511 MB), skipped on rerun, refused a changed configuration, and reproduced the pilot's outputs byte for byte. The only difference was `inputs.json`, which now also records the utilisation setting.

## 3. Pilot results under the corrected workload (ρ = 1.0) — 3 failures, functional only

| Policy | On time % (all) | On time % (never-failing hosts) | Mean queueing (h) | Overhead % | Lost work (h) |
|---|---|---|---|---|---|
| E1 none | 99.92 | 100 | 0.04 | 0 | 133.0 |
| E2 fixed 1 h | **49.66** | **49.67** | 26.7 | 8.21 | 1.8 |
| E3 adaptive 1 h | 66.58 | 66.65 | 19.3 | 7.72 | 0.3 |
| E2 fixed 4 h | 92.43 | 92.47 | 6.3 | 1.96 | 9.4 |
| E3 adaptive 4 h | 96.66 | 96.71 | 4.5 | 1.84 | 0.7 |
| E2 fixed 12 h | 100 | 100 | 1.8 | 0.57 | 8.2 |
| E3 adaptive 12 h | 99.64 | 99.67 | 1.3 | 0.55 | 3.7 |
| E2 fixed 24 h | 99.95 | 100 | 0.7 | 0.22 | 35.0 |
| E3 adaptive 24 h | 100 | 100 | 0.5 | 0.24 | 4.8 |
| E2 fixed 72 h | 99.95 | 100 | 0.15 | 0.05 | 60.4 |
| E3 adaptive 72 h | 100 | 100 | 0.09 | 0.05 | 11.9 |

Full table, split by failing / non-failing hosts: `validation/pilot_summary.csv`. Each failure: `validation/per_failure.csv`.

### Distribution shift (`validation/tier_occupancy.csv`, `checkpoints_by_tier.csv`)

Host-days 1–30, using the validation-derived thresholds (not adjusted):

| Hosts | Host-days | LOW | MEDIUM | HIGH |
|---|---|---|---|---|
| All | 59,520 | 53.76 % | 39.58 % | 6.66 % |
| Failing (3 hosts) | 90 | 0 % | 4.44 % | **95.56 %** |
| Never failing | 59,430 | 53.84 % | 39.63 % | 6.53 % |
| *Validation design target* | — | *90 %* | *9 %* | *1 %* |

* For E3 at T₀ = 4 h, **HIGH-tier checkpoints on never-failing hosts cost 9,634 h of overhead** (115,602 checkpoints), against 1,893 h for the same host-days under E2.
* LOW-tier overhead falls from 15,094 h under E2 to 5,549 h under E3.

The ranking is informative (failing hosts are HIGH 96 % of the time), but the June score shift places 6.5 % of healthy host-days in HIGH instead of about 1 %. This is a **distribution-shift limitation**, to be reported with the full results. Thresholds were not changed.

## 4. Decision needed: arrival spacing (nominal utilisation ρ)

The approved settings do not specify how far apart jobs arrive. I implemented **ρ = 1.0**, nominal back-to-back arrivals, as the default. At ρ = 1, a host has **no idle time**, so any checkpoint overhead accumulates as an ever-growing queue. Deadline misses then mostly measure that backlog, not failures:

* at T₀ = 1 h, half of all jobs on **never-failing** hosts miss their deadline;
* the last job finishes on day 50.

Sensitivity check on the same shard (`validation/utilization_sensitivity.csv`). Lower ρ means fewer jobs fit before the cutoff: 22,484 / 20,380 / 18,265 jobs.

| Policy | On time % (never-failing hosts) at ρ = 1.0 | at ρ = 0.9 | at ρ = 0.8 |
|---|---|---|---|
| E2 fixed 1 h | 49.67 | 100 | 100 |
| E3 adaptive 1 h | 66.65 | 95.51 | 96.48 |
| E2 fixed 4 h | 92.47 | 100 | 100 |
| E3 adaptive 4 h | 96.71 | 100 | 100 |
| all T₀ ≥ 12 h | ≥ 99.67 | 100 | 100 |

With 10–20 % slack, queueing on healthy hosts disappears for every policy except E3 at T₀ = 1 h. There, HIGH-tier hosts checkpoint every 12.2 min (about 29 % overhead), which genuinely exceeds the slack.

**Options:**
* **(a) Keep ρ = 1.0.** Deadline misses then reflect overload as well as failure handling. Report it as a saturated-system scenario.
* **(b) Use ρ = 0.9 (or 0.8) as the primary setting.** Deadline misses then reflect failures and genuinely excessive checkpointing. Report ρ = 1.0 as a sensitivity case.

**My recommendation is (b) with ρ = 0.9, plus ρ = 1.0 as sensitivity.** The full run would take about twice as long. The code supports both through `--utilization`; nothing was changed in the approved defaults.

## 5. Full-run plan (after the decision)

* `python -I research/scripts/run_full.py --out results/full --utilization <ρ>`, for shards 0–55. Each shard runs E1, E2 × 5 and E3 × 5 on one shared plan.
* **Estimated cost:** about 5 min per shard (driver measurement on shard 0), so about 4.5–5 h per ρ, with about 5.2 GB of output per ρ. Peak heap is ≤ about 0.5 GB of the 1.5 GB limit.
* **After the run:** aggregate the results and compute:
  * paired policy comparisons on the identical job set;
  * bootstrap 95 % CIs, resampling hosts (clusters), with lost work driven by about 175 failure events;
  * failing / never-failing and per-tier breakdowns;
  * tier occupancy and the distribution-shift section.

  No significance claims will be made beyond what the intervals support. The aggregation and statistics script will be written once the full outputs exist, since its inputs are fixed by the validated per-shard formats above.

## 6. Commands used

From `project/cloudsim/`:

```
bash research/scripts/build_and_test.sh                                     # 90 / 90
bash research/scripts/run_pilot.sh results/pilot/run1
bash research/scripts/run_pilot.sh results/pilot/run2
PRED=<scratch label-scrambled copy> bash research/scripts/run_pilot.sh results/pilot/check_labels_scrambled --t0 4
bash research/scripts/run_pilot.sh results/pilot/check_no_failures --t0 4 --no-failures
python -I research/validation/validate_pilot.py results/pilot                # 19 / 19
bash research/scripts/run_pilot.sh results/pilot/sensitivity_utilization_0.9 --utilization 0.9
bash research/scripts/run_pilot.sh results/pilot/sensitivity_utilization_0.8 --utilization 0.8
python -I research/scripts/run_full.py --out <scratch> --only 0             # driver test (run, resume, refusal)
```

Runtime per pilot invocation: about 2 min for 11 policy runs, with peak heap 149–525 MB per run.
