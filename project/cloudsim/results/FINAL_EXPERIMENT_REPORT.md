# Final Experiment Report — RF-Based Adaptive Checkpointing in CloudSim

**Project:** Predictive Disk Failure-Aware Adaptive Checkpointing for Fault-Tolerant Cloud Task Scheduling
**Scope:** the full trace-driven CloudSim 3.0.3 experiment over all 56 host shards, under two workload conditions:
* **ρ = 0.9:** the primary result;
* **ρ = 1.0:** a saturated-system sensitivity experiment.

> **Simulation abstraction.** Each Backblaze drive is one simulated host, and a recorded **disk** failure is treated as the failure of that simulated host. This is a trace-driven modelling assumption, not evidence that physical servers failed. All results describe this abstraction.

---

## 1. Summary of findings

1. **Both experiments ran in full and validated cleanly.**
   * Each covers 56 / 56 shards, 110,848 hosts and 175 failure events.
   * Jobs: 1,141,653 at ρ = 0.9 and 1,259,916 at ρ = 1.0.
   * Every shard passed every independent check, and re-runs of the two shards with the most failures reproduced identical output hashes in both scenarios.
2. **At ρ = 0.9 with T₀ = 4 h and 12 h, the RF-adaptive policy (E3) improved on the fixed policy (E2) in both directions at once.**
   * Checkpoint overhead was lower: −6.2 % and −4.2 %.
   * Lost computation was lower: −20.5 % and −23.9 %.
   * Deadline outcomes were unchanged.
   * All 95 % host-clustered bootstrap intervals for these differences exclude zero. The lost-work intervals are wide because they rest on 175 failures.
3. **At T₀ = 24 h and 72 h, E3 trades overhead for protection:** overhead is 7.8 % and 10.4 % higher, while lost work is about 21 % and 29 % lower. For 24 h the lost-work interval includes zero.
4. **At T₀ = 1 h, E3 is harmful.** HIGH-tier hosts checkpoint every 12.2 min, about 29 % overhead. Even with 10 % slack, those hosts build queues and 4.5 % of all jobs miss their deadline, whereas E2 at 1 h misses none.
5. **The model ranks risk usefully, but its June score distribution is shifted.**
   * Failing hosts spent 52.3 % of their host-days in HIGH, and 110 of the 175 failures occurred while the host was HIGH.
   * But 6.5 % of healthy host-days were also HIGH, against about 1 % on validation, and only 54 % of host-days were LOW, against 90 %.
   * The shift makes E3 spend extra overhead on healthy HIGH-tier hosts. The **27 failures (15 %) that occurred in the LOW tier lose more work under E3** than under E2.
6. **At realistic disk failure rates, checkpoint overhead dominates total waste.**
   * With no checkpointing (E1), lost work is only 0.011 % of useful compute at ρ = 0.9. Every checkpointing policy wastes more time in total.
   * The value of checkpointing here lies in **protecting the individual jobs that hit a failure.** E1 misses 19.8 % of deadlines on failing hosts at ρ = 0.9; E2 and E3 at 4 h miss none.
7. **Without nominal slack (ρ = 1.0), adaptive still beats fixed at T₀ = 4 h for the system overall,** with fewer deadline misses (3.23 % vs 7.64 %) and less queueing. But it **shifts the burden onto HIGH-tier hosts, including the failing ones.** Deadline misses on failing hosts rise from 14.9 % to 25.5 % at T₀ = 4 h. Saturation turns the extra HIGH-tier overhead into queueing delay.

No claim of statistical significance is made. "Interval excludes zero" is reported descriptively, without correction for the many comparisons (§7).

---

## 2. Experimental configuration (all as approved; nothing changed)

| Item | Value |
|---|---|
| Simulator | CloudSim 3.0.3 (official jar, unmodified), custom broker, failure injector and spare pool in `project/cloudsim/research/`. Compiled with JDK 24 `javac --release 8`, run on Java 1.8.0_501 |
| Hosts | 110,848 drives from `test_predictions.csv.gz` (June 2019). 1 host = 1 VM = 1 PE at 1000 MIPS; 50 hosts per datacenter entity |
| Shards | 56 deterministic shards, `crc32(serial_number) % 56`. Shards only partition the host population |
| Risk input | RF prior-corrected score. The score of day d applies from 00:00 of day d+1; missing days carry the last score forward; MEDIUM before any score. Labels are never read |
| Risk tiers | LOW < 0.000234 ≤ MEDIUM < 0.001732 ≤ HIGH (validation P90 / P99; **not tuned on June**) |
| Policies | **E1** no checkpointing. **E2** fixed interval T₀. **E3** adaptive: LOW 2.65 T₀, MEDIUM T₀, HIGH T₀ ÷ 4.9. T₀ ∈ {1, 4, 12, 24, 72} h, so 11 policy configurations |
| Costs | Checkpoint save C = 300 s; restore R = 300 s; failure detection D = 60 s; replacement boot B = 120 s |
| Failures | 175 June drive failures in the pool, at `day + crc32("fail\|"+serial) mod 86400` s, identical for all policies. Read only by the failure injector |
| Recovery | The job resumes from its last completed checkpoint on a spare host (never fails, MEDIUM tier). With no checkpoint it restarts from zero (D + B, no R) |
| Workload | Generated **once per shard per scenario** and shared by all 11 policies:<br>• job lengths 24 / 72 / 168 h (p = 0.5 / 0.3 / 0.2);<br>• predetermined submit times `submitⱼ₊₁ = submitⱼ + Lⱼ / ρ` from the host's first day, while `submit < 30 days`;<br>• FIFO queue per host; deadline = submit + 1.5 L;<br>• every job drains to completion and is marked on time or late |
| Scenarios | **ρ = 0.9 (primary):** 10 % nominal idle slack. **ρ = 1.0 (sensitivity):** back-to-back, no slack |
| Statistics | Paired, host-clustered Poisson bootstrap: B = 2,000, seed 20190601, one weight per host applied to both policies of a comparison. Percentile 95 % CIs. Strata (failing / non-failing hosts) bootstrapped separately. **Shards are not treated as samples** |

**Raw totals are not compared between ρ = 0.9 and ρ = 1.0.** The scenarios have different workloads: 1,141,653 vs 1,259,916 jobs, with different submit times. Comparisons are always paired **within** a scenario; across scenarios only the direction and size of within-scenario effects are compared.

## 3. Execution: completion, runtime, memory

| | ρ = 0.9 | ρ = 1.0 |
|---|---|---|
| Shards completed | **56 / 56** (manifest: all DONE) | **56 / 56** (all DONE) |
| Hosts / jobs / failure events | 110,848 / 1,141,653 / 175 | 110,848 / 1,259,916 / 175 |
| Elapsed time (2 shards in parallel) | 1.37 h | 1.67 h |
| Total shard compute | 2.68 h | 3.26 h |
| Wall time per shard (min / median / max) | 89 / 186 / 239 s | 120 / 139 / 530 s |
| Peak Java heap (any policy run) | 431 MB | 417 MB |
| Output (logs, per-job, per-host and event records) | 4.5 GB | 5.1 GB |

Every shard folder holds `DONE`, `OUTPUT_SHA256.txt` (71 files), `workload.csv`, `streams.csv`, `tier_timeline.csv`, `injector_failures.csv`, `inputs.json`, `resources.csv`, and for each of the 11 policies: `jobs.csv`, `hosts.csv`, `checkpoint_events.csv.gz`, `failure_events.csv`, `recovery_events.csv` and `run_info.json`. Per-shard status, timings, memory and hashes are in each run's `manifest.csv`.

## 4. Validation

### 4.1 Before the full run

* **Scenario tests:** 90 / 90 hand-calculated checks pass (`research/scripts/build_and_test.sh`).
* **Pilot:** 19 / 19 independent checks pass, including:
  * byte-identical outputs with about 50 % of labels scrambled;
  * identical decisions before the first failure with and without the failure trace;
  * byte-identical repeat runs.

### 4.2 Full runs (`research/validation/validate_full.py`, independent Python recomputation)

**Result: 56 / 56 shards pass all checks at both ρ = 0.9 and ρ = 1.0. 0 failed checks.** The independent count of June failures in the pool is 175, equal to the failures injected.

Checks run on every shard:
* output-hash integrity;
* hosts = independent shard membership; score counts and first days;
* **score timing without look-ahead and carry-forward**, on 3.3 M host-days per scenario;
* failure events = independent recomputation;
* **workload = independent regeneration with the scenario's ρ**;
* **all 11 policies processed exactly the planned job set** (ids, host, length, submit time);
* overhead = 300 s × checkpoints = checkpoint-log count for every job;
* recovery timing (D + B, + R);
* lost work = time since the last completed checkpoint;
* replacement hosts;
* deadline and state consistency;
* planned = submitted = finished;
* FIFO order;
* the per-job time identity: turnaround = queue + L + overhead + lost + interrupted write + recovery.

**Determinism.** The two shards with the most failures (36 and 18) were re-run from scratch in each scenario. All 71 output-file hashes per shard were identical to the recorded ones.

**Two validator defects were found and fixed during this stage. The simulator outputs were unchanged and both scenarios were fully re-validated afterwards.**
1. The per-shard `all_pass` flag ignored NumPy booleans. As a result, it reported PASS for ρ = 1.0 shard 27 even though one check was false.
2. That false check (lost work, shard 27, E2 at T₀ = 1 h) was caused by an exact tie. A checkpoint completed at t = 2,022,601.0 s, the same second as the host's failure. CloudSim processed the completion first, so the simulator correctly recorded 0 lost work, but the validator only accepted checkpoints strictly *before* the failure. The check now uses ≤.

## 5. Primary results: ρ = 0.9 (`results/full_rho0.9/analysis/`)

### 5.1 Policy outcomes, all hosts (110,848 hosts, 1,141,653 jobs)

| Policy | Deadline miss % | Lost work (h) | Checkpoint overhead (h) | Wasted % of useful | Mean queueing (h/job) | Checkpoints per job | Recovery (h) |
|---|---|---|---|---|---|---|---|
| E1 none | 0.031 | 8,375 | 0 | 0.011 | 0.019 | 0 | 7.8 |
| E2 1 h | 0 | 96.0 | 6,293,612 | 8.209 | 0 | 66.15 | 22.8 |
| E3 1 h | **4.537** | 78.7 | 5,852,951 | 7.635 | 2.299 | 61.52 | 23.0 |
| E2 4 h | 0 | 317.8 | 1,502,050 | 1.960 | 0 | 15.79 | 20.2 |
| E3 4 h | 0 | **252.5** | **1,409,313** | **1.839** | 0 | 14.81 | 21.3 |
| E2 12 h | 0 | 871.3 | 437,258 | 0.572 | 0.0001 | 4.60 | 18.9 |
| E3 12 h | 0.0002 | **662.8** | **419,017** | **0.547** | 0.0002 | 4.40 | 19.0 |
| E2 24 h | 0.0025 | 1,752.6 | 171,060 | 0.225 | 0.0008 | 1.80 | 16.6 |
| E3 24 h | 0.0031 | 1,390.0 | 184,379 | 0.242 | 0.0014 | 1.94 | 18.0 |
| E2 72 h | 0.0147 | 4,627.2 | 37,986 | 0.056 | 0.0063 | 0.40 | 11.2 |
| E3 72 h | 0.0091 | 3,297.7 | 41,935 | 0.059 | 0.0056 | 0.44 | 15.5 |

* Wasted = overhead + lost + interrupted writes + recovery.
* Recovery hours vary slightly by policy because a failure that strikes an idle host costs no job recovery: 20 of the 175 failures under E1. Whether a host is idle at its failure time depends on how far behind its queue is.
* Full table with CIs and strata: `policy_summary.csv`.

### 5.2 Paired comparison E3 − E2 at equal T₀, all hosts (`paired_comparisons.csv`)

95 % CIs from the paired host-clustered bootstrap. ✔ = interval excludes 0.

| T₀ | Δ overhead (h) | Δ lost work (h) | Δ wasted (pp of useful) | Δ deadline miss (pp) | Δ queueing (h/job) |
|---|---|---|---|---|---|
| 1 h | −440,661 [−467,886, −412,600] ✔ | −17.3 [−33.4, −0.1] ✔ | −0.575 [−0.611, −0.539] ✔ | **+4.537 [4.450, 4.625] ✔** | +2.30 [2.25, 2.35] ✔ |
| **4 h** | **−92,736 [−99,504, −85,803] ✔** | **−65.3 [−126.4, −1.3] ✔** | **−0.121 [−0.130, −0.112] ✔** | 0 | 0 |
| **12 h** | **−18,241 [−20,459, −15,976] ✔** | **−208.5 [−402.1, −12.9] ✔** | **−0.024 [−0.027, −0.021] ✔** | +0.0002 [0, 0.0004] | +0.0001 (n.s.) |
| 24 h | +13,319 [12,226, 14,446] ✔ | −362.6 [−726.5, +7.2] | +0.017 [0.015, 0.018] ✔ | +0.0006 [−0.0015, 0.0028] | +0.0006 (n.s.) |
| 72 h | +3,950 [3,596, 4,313] ✔ | −1,329.5 [−2,171.9, −477.8] ✔ | +0.0034 [0.0023, 0.0046] ✔ | −0.0056 [−0.0108, −0.0004] ✔ | −0.0006 (n.s.) |

### 5.3 Failing vs non-failing hosts (ρ = 0.9)

| Stratum | Policy | Deadline miss % | Lost work (h) | Overhead % of useful | Checkpoints per job |
|---|---|---|---|---|---|
| **Failing hosts (175)** | E1 none | **19.81** | 8,375 | 0 | 0 |
| | E2 4 h / E3 4 h | 0 / 0 | 317.8 / 252.5 | 1.96 / 3.18 | 15.8 / 25.6 |
| | E2 12 h / E3 12 h | 0 / 0.11 | 871.3 / 662.8 | 0.57 / 0.99 | 4.6 / 8.0 |
| | E2 72 h / E3 72 h | 9.40 / **5.82** | 4,627 / **3,298** | 0.05 / 0.12 | 0.41 / 0.98 |
| | E2 1 h / E3 1 h | 0 / **23.34** | 96.0 / 78.7 | 8.21 / 11.94 | 66.2 / 96.4 |
| **Non-failing hosts (110,673)** | E2 4 h / E3 4 h | 0 / 0 | 0 / 0 | 1.959 / **1.836** | 15.79 / 14.80 |
| | E2 12 h / E3 12 h | 0 / 0 | 0 / 0 | 0.570 / **0.546** | 4.60 / 4.40 |
| | E2 24 h / E3 24 h | 0 / 0 | 0 / 0 | 0.223 / 0.240 | 1.80 / 1.94 |
| | E2 1 h / E3 1 h | 0 / **4.51** | 0 / 0 | 8.21 / 7.63 | 66.2 / 61.5 |

**On failing hosts,** E3 checkpoints more (they are mostly HIGH) and loses less work. The E3 − E2 lost-work difference at 4 h is −65.3 h [−124.9, +0.9] within this stratum. At 72 h, E3 reduces failing-host deadline misses by 3.6 pp [−6.7, −0.2].

**On non-failing hosts,** E3 saves overhead at T₀ ≤ 12 h because 54 % of their host-days are LOW, and costs overhead at T₀ ≥ 24 h.

### 5.4 Comparison with no checkpointing (E1), ρ = 0.9

* Every E2 and E3 configuration reduces lost work by 3,748–8,297 h relative to E1, and every CI excludes 0.
* Every configuration except E3 at 1 h also removes most of E1's deadline misses (0.031 % of all jobs, 19.8 % on failing hosts).
* The cost is far larger in total: wasted time rises from 0.011 % (E1) to 0.056–8.2 % of useful compute, depending on policy and T₀.

At these failure rates, checkpointing never pays off in **aggregate** compute time; it pays off only in **per-job protection** for the jobs that a failure hits. This matches the Young/Daly expectation in the design document (§6.3).

## 6. Sensitivity results: ρ = 1.0 (saturated, no nominal slack) — `results/full_rho1.0/analysis/`

| Policy | Deadline miss % | Lost work (h) | Overhead % of useful | Mean queueing (h/job) | Mean turnaround / length |
|---|---|---|---|---|---|
| E1 none | 0.056 | 9,603 | 0 | 0.04 | 1.001 |
| E2 1 h / E3 1 h | 50.74 / **34.23** | 96.8 / 78.7 | 8.21 / 7.75 | 26.8 / 19.1 | 1.78 / 1.58 |
| E2 4 h / E3 4 h | 7.64 / **3.23** | 354.0 / **278.7** | 1.96 / **1.84** | 6.37 / **4.44** | 1.19 / 1.13 |
| E2 12 h / E3 12 h | 0.011 / **0.265** | 1,058.0 / **726.5** | 0.570 / **0.547** | 1.82 / **1.24** | 1.05 / 1.04 |
| E2 24 h / E3 24 h | 0.024 / 0.017 | 2,031.4 / 1,670.7 | 0.223 / 0.237 | 0.69 / 0.52 | 1.02 / 1.02 |
| E2 72 h / E3 72 h | 0.042 / 0.028 | 5,136.2 / 3,687.2 | 0.050 / 0.052 | 0.16 / 0.10 | 1.004 / 1.003 |

**Paired E3 − E2 at ρ = 1.0, all hosts:**

| T₀ | Δ deadline miss (pp) | Δ lost work (h) | Δ overhead (h) | Δ queueing (h/job) |
|---|---|---|---|---|
| 1 h | −16.51 [−16.61, −16.41] ✔ | −18.1 [−35.8, +0.3] | −390,261 ✔ | −7.77 ✔ |
| 4 h | −4.41 [−4.48, −4.33] ✔ | −75.2 [−138.4, −6.2] ✔ | −97,844 ✔ | −1.93 ✔ |
| 12 h | **+0.254 [0.238, 0.271] ✔** | −331.5 [−525.0, −143.7] ✔ | −20,071 ✔ | −0.58 ✔ |
| 24 h | −0.0071 [−0.0137, −0.0008] ✔ | −360.7 [−769.3, +43.2] | +11,749 ✔ | −0.17 ✔ |
| 72 h | −0.0136 [−0.0206, −0.0068] ✔ | −1,449.0 [−2,300.2, −571.1] ✔ | +1,669 ✔ | −0.06 ✔ |

**Failing hosts at ρ = 1.0 (E3 − E2 deadline miss, pp):**

| T₀ | Difference [95 % CI] |
|---|---|
| 1 h | +8.1 [5.3, 11.3] |
| 4 h | **+10.6 [7.7, 13.6]** (25.5 % vs 14.9 %) |
| 12 h | +1.8 [−1.3, 4.8] |
| 24 h | −4.5 [−8.2, −0.6] |
| 72 h | −8.6 [−12.5, −4.6] |

**Risk-tier view at T₀ = 4 h, ρ = 1.0** (hosts grouped by their majority June tier; `tier_breakdown.csv`):

| Hosts (majority tier) | E2 deadline miss | E3 deadline miss |
|---|---|---|
| Healthy, LOW (92,451) | 7.65 % | **1.72 %** |
| Healthy, HIGH (2,584) | 7.53 % | **34.93 %** |
| Failing, HIGH (96) | 15.2 % | **32.6 %** |

The failing HIGH hosts' lost work falls from 206.4 h to 47.3 h, but their deadline misses rise to 32.6 %.

### Do the adaptive benefits survive without slack?

**Partly.**
* At ρ = 1.0, every checkpoint adds directly to a queue that never drains. Any overhead saving therefore becomes a deadline benefit.
* That is why E3 at 4 h gives the **largest system-wide improvement** of the whole study: −4.4 pp of deadline misses, with less lost work and less overhead.
* The same mechanism **penalises HIGH-tier hosts.** Their extra checkpoints (about 4–7 % overhead at T₀ = 4 h) build long queues. Since the failing hosts are mostly HIGH, their deadline outcomes get **worse** under E3 at T₀ ≤ 4 h, even though their lost work falls.
* With 10 % slack (ρ = 0.9), that extra overhead is absorbed and the failing hosts' deadlines are unaffected at 4–12 h.
* **Conclusion:** the per-job protection benefit of adaptive checkpointing depends on HIGH-risk hosts having spare capacity. Under saturation, the policy should be paired with load relief for high-risk hosts (for example, reduced admission or migration). That was outside this study's scope.

## 7. Risk tiers and distribution shift

### 7.1 Tier occupancy, host-days 1–30 (identical in both scenarios; `tier_occupancy.csv`)

| Hosts | Host-days | LOW | MEDIUM | HIGH |
|---|---|---|---|---|
| All (110,848) | 3,325,440 | 54.09 % | 39.31 % | 6.61 % |
| Failing (175) | 5,250 | 24.78 % | 22.91 % | **52.31 %** |
| Non-failing (110,673) | 3,320,190 | 54.14 % | 39.33 % | 6.53 % |
| *Validation design target* | — | *90 %* | *9 %* | *1 %* |

* **Hosts by majority tier:** 92,493 LOW, 15,675 MEDIUM, 2,680 HIGH. Among failing hosts: 96 HIGH, 37 MEDIUM, 42 LOW.
* **Tier at the moment of failure:** HIGH 110 (62.9 %), MEDIUM 38 (21.7 %), LOW 27 (15.4 %).

### 7.2 Where the overhead and lost work go (ρ = 0.9, `checkpoints_by_tier.csv`, `failures_detail.csv`)

* **Overhead on non-failing hosts at T₀ = 4 h, E2 → E3:**
  * LOW tier: 774,091 h → 283,055 h (**−491,036 h**);
  * HIGH tier: 96,603 h → 492,118 h (**+395,515 h**);
  * MEDIUM: unchanged (629,001 h → 630,322 h).

  The net saving comes from LOW hosts. Most of it is spent again on the 6.5 % of healthy host-days that the shifted scores place in HIGH.
* **Lost work at T₀ = 4 h, by tier at failure, E2 → E3:**
  * HIGH: 203.2 h → **53.2 h**;
  * MEDIUM: 66.2 h → 75.6 h;
  * LOW: 48.4 h → **123.7 h**.

  At T₀ = 12 h: HIGH 539.1 → 102.2 h, LOW 135.3 → 395.0 h. The policy works where the model is right, and **costs more where the model misses a failure**, because LOW intervals are 2.65 × longer.

### 7.3 Interpretation

* The thresholds were set on validation (May) and, as approved, were **not** re-tuned on June.
* June scores are shifted upward, consistent with the Phase 2 calibration finding: mean predicted 0.046 % vs 0.019 % on validation. So the HIGH tier is about 6.6 times larger than intended.
* The ranking still separates failing hosts well (52 % of their host-days HIGH vs 6.5 % for healthy hosts). But the tier sizes, and with them E3's overhead budget, are not what the design assumed.
* This distribution shift is a primary limitation. Any deployment would need tier boundaries re-estimated on recent data, or set by a target share.

## 8. Limitations

1. **Disk-to-host abstraction:** results are about drive-failure-driven host failures in simulation, not about real server availability.
2. **Few failures:** 175 failure events, so every lost-work estimate has wide intervals (often ±50 % or more). Overhead differences are estimated precisely because they involve about 111 k hosts.
3. **Distribution shift:** 6.6 % HIGH host-days instead of about 1 % (§7). The adaptive policy's overhead on healthy hosts is inflated accordingly.
4. **One month, one fleet:** bootstrap intervals describe host-level variability within June 2019 Backblaze drives, not other periods or fleets.
5. **Workload model:** a synthetic 24 / 72 / 168 h job mix with FIFO queues and fixed costs (C = R = 300 s, D = 60 s, B = 120 s). Results, especially at ρ = 1.0, depend on the arrival spacing; the two ρ values bracket that dependence.
6. **Simplifications:**
   * spare hosts never fail and are MEDIUM;
   * drives leaving without a failure stay up;
   * the failure time within the day is a hash offset (sensitivity offsets were not run);
   * daily risk granularity;
   * no proactive migration.
7. **Multiplicity:** 15 policy comparisons × about 14 metrics × 3 strata × 2 scenarios. Intervals are not adjusted, so isolated "excludes zero" results should not be read as confirmed effects.
8. **CloudSim artefacts:** ≤ 0.22 s timing jitter between neighbouring hosts after a failure, and ≤ 1.6 s per job of event granularity. Both are negligible at the hour scale of the results.

## 9. Research conclusions

* **Answer to the research question (primary, ρ = 0.9):** RF-based adaptive checkpointing **can** beat fixed-interval checkpointing. At the moderate intervals T₀ = 4–12 h it lowered **both** checkpoint overhead (−4 to −6 %) and lost computation (−20 to −24 %), without any deadline cost, in a paired comparison on an identical workload with identical failures.
* At long intervals (24–72 h) it buys lower lost work at slightly higher overhead.
* At very short intervals (1 h) its HIGH-tier interval of about 12 min is counter-productive.
* **The benefit is bounded by the predictor's errors and by the June distribution shift.**
  * Failures the model ranks HIGH lose far less work.
  * Failures it misses (LOW tier, 15 %) lose more.
  * About 6.5 % of healthy host-days receive costly HIGH-tier checkpointing.
* **Under saturation (ρ = 1.0),** the adaptive policy still improves system-wide deadline performance at T₀ = 4 h. However, it **worsens deadline outcomes on the high-risk and failing hosts it is meant to protect,** because there is no slack to absorb their extra checkpoints.
* **For the paper:**
  * present adaptive checkpointing as a **Pareto improvement at moderate T₀ under non-saturated load**;
  * report the saturation penalty and the dependence on predictor calibration as the key conditions;
  * be clear that, at realistic disk failure rates, checkpointing of any kind is justified by per-job protection rather than by aggregate efficiency.

## 10. Reproduction and files

From `project/cloudsim/`:

```
bash research/scripts/build_and_test.sh                                        # 90 / 90
python -I research/scripts/run_full.py --out results/full_rho0.9 --utilization 0.9 --workers 2
python -I research/validation/validate_full.py results/full_rho0.9 --workers 3
python -I research/validation/analyze_full.py  results/full_rho0.9 --boot 2000 --workers 1
python -I research/scripts/run_full.py --out results/full_rho1.0 --utilization 1.0 --workers 2
python -I research/validation/validate_full.py results/full_rho1.0 --workers 3
python -I research/validation/analyze_full.py  results/full_rho1.0 --boot 2000 --workers 1
```

| Path | Content |
|---|---|
| `results/full_rho{0.9,1.0}/manifest.csv`, `run_config.json`, `shard_KK.log` | Per-shard status, timings, memory, input and output hashes; driver logs |
| `results/full_rho{…}/shard_KK/` | Per-shard inputs, workload, per-job / per-host records, checkpoint / failure / recovery event logs, `OUTPUT_SHA256.txt` |
| `results/full_rho{…}/validation/` | `validation_by_shard.csv`, `validation_summary.json` |
| `results/full_rho{…}/analysis/` | `policy_summary.csv`, `paired_comparisons.csv`, `tier_breakdown.csv`, `tier_occupancy.csv`, `checkpoints_by_tier.csv`, `failures_detail.csv`, `analysis_meta.json` |
| `results/full_rho{…}.driver.log`, `.validation.log`, `.analysis.log` | Run, validation and analysis logs |
| `results/pilot/` | Validated pilot (v2) with `PILOT_REPORT.md`; the superseded v1 pilot is in `results/pilot_v1_superseded/` |
