# Phase 3 Design — RF-Based Adaptive Checkpointing in CloudSim

**Project:** Predictive Disk Failure-Aware Adaptive Checkpointing for Fault-Tolerant Cloud Task Scheduling
**Status:** DESIGN ONLY. Nothing is implemented yet. The ML pipeline, model, dataset and prediction files are unchanged.
**Inputs:** the Phase 2 outputs in `project/ml/models/` and `project/ml/results/model_evaluation/`.

> **Addendum (after setup; see `SETUP_LOG.md`).** CloudSim 3.0.3 is now installed and the core mechanism passes 65 / 65 scenario checks. Two decisions differ from this design:
> * **Checkpoint mechanism:** CloudSim 3.0.3's cloudlet pause/resume is buggy (`SETUP_LOG.md` §6). So the §7 fallback is used: compute segments plus separate C-second checkpoint cloudlets.
> * **Sharding:** about 2,000 hosts per shard (K ≈ 56) instead of K = 8. Runtime grows faster than linearly with shard size (`SETUP_LOG.md` §7).
>
> The approved settings in §6–§9 (thresholds 0.000234 / 0.001732, ratios 2.65 / 4.9, C = R = 300 s, D = 60 s, B = 120 s, jobs of 24 / 72 / 168 h, deadline 1.5 × L, T₀ sweep) are implemented unchanged.

**Legend:**
* **[FOUND]** — inspected on this machine.
* **[DATA]** — measured from the project's files.
* **[KNOWLEDGE — verify]** — from general knowledge of CloudSim; to be confirmed once the library is in place.
* **[PROPOSAL]** — a design choice for review.

---

## 1. Existing CloudSim version and architecture  [FOUND]

| Item | Finding |
|---|---|
| `project/cloudsim/` | **Empty**: no source, jar or build file |
| CloudSim elsewhere on the machine | **None found.** The project, Desktop, Downloads, Documents and OneDrive were searched (depth ≤ 7) for `*cloudsim*` / `*cloudbus*`; there is no `~/.m2` CloudSim artifact and no `pom.xml` or `build.gradle` |
| Java | **JDK 24.0.2** (`javac` available); a Java 8 JRE is also installed |
| Build tools | **No Maven, no Gradle.** The only IDE found is PyCharm Community |

**So there is no existing CloudSim version or architecture to extend.** A version must be chosen and obtained, which requires your approval to download.

### 1.1 Version options  [KNOWLEDGE — verify]

| Option | Pros | Cons |
|---|---|---|
| **A. Classic CloudSim 3.0.3** (Cloudbus, 2013) — *recommended* | The most-cited CloudSim release in the literature. One jar plus Apache Commons Math, so it builds with plain `javac` (no Maven). Stable API: `SimEntity`, `DatacenterBroker` subclassing, cloudlet submit / cancel / pause / resume, custom event tags | Old code (Java 6/7 era): needs a compile check on JDK 24. No fault tolerance built in |
| B. Classic CloudSim 6.x / 7G (Cloudslab, newer) | Maintained modern line of the same simulator | Maven project, so Maven must be installed. API differences from 3.0.3 to be checked |
| C. CloudSim Plus 8.x | Modern; has a `HostFaultInjection` module | **A separate framework (a fork), which you asked to avoid.** Its fault injection is random (Poisson), not trace-driven, and it has no cloudlet checkpointing either |

**Recommendation:** Option A, because it is closest to "CloudSim" as cited and needs the least tooling. Option B if a maintained version is preferred and Maven may be installed.

### 1.2 Native support for what this experiment needs  [KNOWLEDGE — verify]

| Need | Classic CloudSim (A/B) | Consequence |
|---|---|---|
| Discrete-event engine, custom entities and events | Yes (`SimEntity`, `CloudSim.send`, custom tags) | Reused as is |
| Datacenter / Host / VM / Cloudlet model | Yes | Reused as is |
| Cancel, pause and resume a running cloudlet | Yes (`CLOUDLET_CANCEL`, `CLOUDLET_PAUSE`, `CLOUDLET_RESUME` events, or broker helpers) | Used to model checkpoint pauses and failures |
| **Host failure injected from a trace** | **No.** At most a "failed" flag on hosts or PEs; nothing kills running VMs or cloudlets | **Custom `FailureInjector` entity** |
| **Checkpointing (save state, restore, resume from last checkpoint)** | **No** | **Custom broker logic** |
| Recovery onto another host | No automatic recovery | **Custom broker logic** plus a spare-host pool |

**Conclusion:** CloudSim provides the event engine and resource model. **Trace-driven failures, checkpointing, lost-work accounting and recovery must all be custom.** This is true of every option above.

## 2. Current implementation status

| Component | Status |
|---|---|
| Disk-failure model (Phase 2) | **Done.** `random_forest_7d.joblib`, the threshold, β and feature order are saved |
| June risk scores | **Done.** `test_predictions.csv.gz`: 2,544,754 rows, 110,848 drives, dates 2019-06-01 … 06-23, columns `serial_number, date, model, source_file_altered, label_primary, score_raw, p_failure_7d_corrected` [DATA] |
| Failure dates | **Available.** `project/ml/results/dataset_audit_revalidation/drive_failure_summary.csv` |
| Training-period risk distribution | **Available.** `project/ml/results/model_evaluation/calibration_validation.csv` (validation 05-11 … 05-24, internal model) |
| CloudSim code, build, experiments | **Not started** |

## 3. Mapping Backblaze drives to CloudSim hosts  [PROPOSAL]

> **Simulation abstraction (to state explicitly in the paper):** each Backblaze drive stands for one simulated CloudSim host. A recorded **disk** failure is treated as a failure of that **simulated** host. This is a trace-driven modelling assumption. It is **not** evidence that a whole physical server failed, and real hosts usually survive a single disk failure.

### 3.1 The host pool  [DATA]

* **Trace hosts:** every drive in `test_predictions.csv.gz`, i.e. 110,848 hosts. 110,607 are present on 06-01; 241 appear later and join on their first observed day.
* **Failure events:** the 175 drives in the pool whose failure record falls in June (06-02 … 06-29).
* **June failure records left out:**

  | Drive | Reason |
  |---|---|
  | ZJV03F45, PL1331LAHD6WVH | Failed 06-01; their pre-failure scores fall in May |
  | ZCH0CJC3 | Quality-excluded |
  | 66GHS5N1S | Only 1 prior observation; its only labelled row would be dated 06-26, after 06-23 |

  Report these 4 events as outside the simulation.

### 3.2 Host and VM specification

All hosts are identical, so the policies differ only in checkpoint behaviour:
* 1 host = 1 VM with 1 PE at 1,000 MIPS;
* space-shared scheduling, so one job runs at a time at full speed;
* RAM, bandwidth and storage generous enough never to constrain.

The drive model (`model` column) is kept only for per-model reporting.

### 3.3 Scale

* 110,848 hosts in one CloudSim run is likely to exceed the ~3 GB memory budget. **Shard** the pool into K deterministic shards by `crc32(serial_number) % K` (e.g. K = 8, about 14k hosts each).
* Run every policy on every shard and add up the results. The shards are independent because each host's work stream is independent (§8).
* A small pilot (one shard) will measure memory and runtime before the full run.

## 4. How the June prediction records are used

1. **Load.** `RiskTraceLoader` streams `test_predictions.csv.gz` (GZIP) and keeps only `serial_number`, `date` and `p_failure_7d_corrected`. **`label_primary` is not read by the simulator** (it is outcome information).
2. **When a score takes effect.** The score for date *d* is computed from SMART data up to and including day *d*. It therefore becomes effective at **00:00 on day d+1** in simulation time, and stays in force until the next score takes effect.
3. **Missing scores.**
   * The prediction file holds only rows whose 7-day outcome was known. Failure-day rows, rows of drives about to leave without failure, and all of 06-24 … 06-30 are absent.
   * If a missing score were treated as a signal, the gaps would leak future information. **Rule:** carry forward the most recent available score. For example, the 06-23 score covers 06-24 … 06-30, which matches its 7-day horizon.
   * A host with no score yet uses the **Medium** tier.
4. **Timestamps and identifiers** are kept as given. Simulation time 0 = 2019-06-01 00:00, measured in seconds. Day *d* starts at `86,400 × (d − 2019-06-01)`.
5. **Tier updates.** A `RISK_UPDATE` event at every midnight updates each host's tier (§6).

## 5. Converting failure dates into simulated failure events

* **Source:** `failure_date` for the 175 pool drives, from `drive_failure_summary.csv`. Failure dates are read **only by `FailureTraceLoader` → `FailureInjector`**. The policy and broker never see them.
* **Time of day:** the failure record is the drive's last daily snapshot, so it failed on day F at an unknown time.
  * **Primary:** `t_fail = 86,400 × (F − 06-01) + offset`, with `offset = crc32("fail|" + serial) mod 86,400` seconds. This is deterministic and **identical in all experiments**.
  * **Sensitivity runs:** offset = 0 (the earliest possible failure) and offset = 86,399 s.
* **Effect:** at `t_fail` the injector sends `HOST_FAILURE(hostId)`. The host is marked failed; its running job loses all progress since its last checkpoint; the job moves to recovery (§7, §8). **A failed host never returns.**
* **Drives that leave the trace without a failure record** are **not** failures. The host simply stays up with its last score carried forward. This is a simplifying assumption; record how many hosts it affects.
* **Consistency with the ML labels:** the score for day F−1 (a positive row) takes effect at 00:00 on day F, before the failure. The failure-day row is never used.

## 6. How the risk score sets the checkpoint interval

### 6.1 Risk tiers (training-period information only)  [DATA]

The corrected scores rank risk well but are **not calibrated** (Phase 2 report, §6.3), so the policy uses **tiers**, not the raw probability.

* **Boundaries** are the 90th and 99th percentiles of the **validation** scores (2019-05-11 … 05-24), from `calibration_validation.csv` (bins 9 and `top_1pct`).
* **No June outcome is used.**

| Tier | Corrected score *p* | Validation share | Observed 7-day failure rate on validation | Implied hazard λ = −ln(1−r)/168 h | Implied MTBF |
|---|---|---|---|---|---|
| **Low** | p < 0.000234 | 90 % | 135 / 1,357,889 = 9.9 × 10⁻⁵ | 5.9 × 10⁻⁷ / h | ≈ 1.69 M h |
| **Medium** | 0.000234 ≤ p < 0.001732 | 9 % | 95 / 135,789 = 7.0 × 10⁻⁴ | 4.2 × 10⁻⁶ / h | ≈ 240 k h |
| **High** | p ≥ 0.001732 | 1 % | 251 / 15,088 = 1.66 × 10⁻² | 1.0 × 10⁻⁴ / h | ≈ 10 k h |
| *(all)* | — | — | 3.19 × 10⁻⁴ | 1.9 × 10⁻⁶ / h | ≈ 527 k h |

**Caveats:**
* The boundaries come from the internal validation model and are applied to the final model's June scores. Phase 2 found that operating points drift between the two (FPR 0.07 % → 0.18 % at the main threshold), so the June tier shares will not be exactly 90 / 9 / 1. Report the actual shares.
* The rates assume a constant hazard within the 7-day window.

### 6.2 Interval rule

| Policy | Interval while the host is in tier k |
|---|---|
| **Fixed** | T₀ in every tier |
| **Adaptive (primary)** | T_Low = 2.65 × T₀, T_Medium = T₀, T_High = T₀ / 4.9 |
| Adaptive (secondary, "absolute Young/Daly") | T_k = √(2 · C · MTBF_k), clamped to [10 min, ∞) |

* **Where the primary ratios come from:** they are the Young/Daly ratios √(MTBF_Low / MTBF_Med) ≈ 2.65 and √(MTBF_Med / MTBF_High) ≈ 4.9, from the validation rates. The medium tier matches the fixed baseline, so the adaptive policy differs from it only where the model says risk is lower or higher. Nothing is tuned on June data.
* **When a host changes tier:** the next checkpoint is due at `last_checkpoint_time + T_new`. If that time has already passed, the checkpoint is taken immediately.

### 6.3 Important consequence for the workload

With the absolute Young/Daly rule and C = 5 min, the intervals are:

| Tier | Interval |
|---|---|
| Low | ≈ 530 h |
| Medium | ≈ 200 h |
| High | ≈ 41 h |
| Population (a "Young-optimal" fixed policy) | ≈ 300 h |

* **For 24-hour jobs, the best fixed policy is effectively "no checkpointing".** At realistic disk failure rates, checkpointing only pays off for long jobs on high-risk hosts.
* The workload must therefore contain **multi-day jobs** (§9.2).
* Results should be reported as a **sweep over T₀**, so the conclusion does not rest on one hand-picked interval.

## 7. Checkpoint saving and recovery  [PROPOSAL]

Parameters, all configurable and identical across experiments:

| Symbol | Meaning | Default |
|---|---|---|
| C | Checkpoint cost: job paused while state is written | 300 s |
| R | Restore cost: checkpoint read on the new host | 300 s |
| D | Failure-detection delay (heartbeat timeout) | 60 s |
| B | Replacement VM provisioning and boot | 120 s |

**Checkpoint mechanism.** The broker keeps one timer per running job.
1. When the timer fires, the broker **pauses** the job's cloudlet. The job is then not progressing.
2. After C seconds the broker **resumes** it and records a checkpoint.
3. The checkpoint holds the committed work W_c, which is the cloudlet's finished length at the moment of the pause.

Progress is read from CloudSim's own cloudlet accounting.

**Fallback mechanism** (if pause/resume turns out unreliable in the chosen version): split each job into segment cloudlets, one per checkpoint interval, with a C-second delay between segments.

**A failure during a checkpoint write** means that checkpoint is lost; the previous checkpoint is used.

**Recovery** after `HOST_FAILURE` at time t_f:
1. Cancel the cloudlet and record its progress at t_f.
2. Lost work = progress at t_f − W_c, or all progress if there is no checkpoint (the no-checkpoint policy).
3. At t_f + D, request a replacement host from the spare pool (§8); it is ready at t_f + D + B.
4. Restore: + R seconds, only if a checkpoint exists. With no checkpoint the job restarts from zero.
5. Submit a cloudlet for the remaining length L − W_c and re-arm the checkpoint timer.

## 8. How tasks resume after a host failure

* **Work streams.** Each trace host carries one **work stream**: a fixed sequence of jobs submitted back to back from the host's first day. Workloads are defined per stream, not per host, so **identical in all experiments**.
* **Spare pool.** On failure, the stream moves to a host from a spare pool: extra hosts per shard, at least as many as the shard's failures, of the same specification. Spare hosts:
  * are not Backblaze drives and are assumed not to fail during the simulation;
  * use the **Medium** tier (they have no SMART history).

  This keeps recovery identical across policies and avoids a recovered job landing on another trace host with its own failure timeline. State the assumption; a variant using trace hosts can be added later if needed.
* **What moves.** The interrupted job resumes from its last checkpoint. Later jobs in the stream run on the spare.
* **No live migration and no proactive migration.** Moving work off high-risk hosts *before* failure is a different strategy and out of scope for this phase.

## 9. Experimental configurations

### 9.1 The three main configurations (same workload, hosts, C/R/D/B and failure events)

| ID | Policy | Checkpoints | On failure |
|---|---|---|---|
| **E1** | No checkpointing | None | Job restarts from zero on a spare host (D + B, no R) |
| **E2** | Fixed interval | Every T₀, in every tier | Resume from last checkpoint (D + B + R) |
| **E3** | RF adaptive | Tier-dependent interval (§6.2, primary) | Resume from last checkpoint (D + B + R) |

### 9.2 Workload  [PROPOSAL]

* **Jobs per stream:** lengths drawn deterministically from {24 h, 72 h, 168 h} with probabilities {0.5, 0.3, 0.2}, via `crc32(serial|jobIndex)`. The lengths are measured as compute time at 1,000 MIPS.
* **Submission:** from 06-01 00:00, or the host's first day, until 06-30 24:00. Jobs still running at the end continue until they finish (drain).
* **Deadline** for each job: submit + 1.5 × L. A job counts as **successful** if it finishes by its deadline.

### 9.3 Sweeps and sensitivity runs

| What varies | Values |
|---|---|
| T₀ | 1, 4, 12, 24, 72 h (E2 and E3 at each value) |
| Secondary adaptive policy | Absolute Young/Daly |
| C = R | 60 s, 300 s, 900 s |
| Failure time within the day | offset 0 / hash / 86,399 s |
| Job lengths | All-24 h vs the mixed workload |
| **Oracle reference** (upper bound only) | Hosts that will fail use the High interval in the 7 days before failure. **Clearly labelled as using future knowledge** |

## 10. Evaluation metrics and formulas

For each job *j*:
* L_j = useful compute (s); s_j = submit time; e_j = finish time;
* n_j = completed checkpoints; f_j = failures the job experienced;
* for each failure *i* of job *j*: p_ji = progress at failure, W_ji = committed work at the last checkpoint before it.

| Metric | Formula | Reported as |
|---|---|---|
| **Checkpoint overhead** | O_j = n_j · C | Total; per job; overhead ratio Σ O_j / Σ L_j |
| **Lost computation** | Lost_j = Σᵢ (p_ji − W_ji), with W_ji = 0 if no checkpoint | Total hours; per failed job |
| **Recovery time** | Rec_j = Σᵢ (D + B + R · 1[checkpoint exists]) | Total; per failure |
| **Job success rate** | Share of submitted jobs with e_j ≤ s_j + 1.5 L_j | % overall; % among jobs that hit a failure |
| **Total execution time** | TT_j = e_j − s_j = L_j + O_j + Lost_j + Rec_j | Mean and P95; sum over streams; makespan per shard |
| **Checkpoints per task** | n_j | Mean / median / max, by tier and by policy |
| Wasted-time ratio | Σ (O_j + Lost_j + Rec_j) / Σ L_j | Main single-number comparison |
| Net benefit vs E1 | Σ TT_j(E1) − Σ TT_j(Ek) | Hours saved (negative = cost) |

Reporting rules:
* **Split every metric** into all jobs / jobs on hosts that failed / jobs on hosts that never failed. About 99.8 % of hosts never fail, so overall averages are dominated by checkpoint overhead. The benefit side (lost work avoided) comes from only **175 failure events**.
* **Uncertainty:** bootstrap 95 % CIs, resampling hosts, especially for lost work.
* **Diagnostics:**
  * tier occupancy over June (actual shares vs the 90 / 9 / 1 target);
  * for each failing host, its tier during the 24 h before failure (how much warning the policy actually had).

## 11. Java classes and responsibilities  [PROPOSAL]

Package `ckpt` under `project/cloudsim/src/main/java/`. Simulation time is in seconds, with 0 = 2019-06-01 00:00.

| Class | Responsibility |
|---|---|
| `config.ExperimentConfig` | Loads `experiment.properties`: C, R, D, B, T₀, tier boundaries and ratios, workload mix, deadline slack, shards, seeds, file paths, policy id |
| `trace.RiskTraceLoader` | Streams the GZIP predictions; builds a `HostRiskTimeline` per serial (day → score); applies the carry-forward rule; **ignores `label_primary`** |
| `trace.HostRiskTimeline` | `scoreEffectiveAt(time)` and `tierAt(time)`, applying the d+1 effectiveness rule |
| `trace.FailureTraceLoader` | Reads `drive_failure_summary.csv`; returns `FailureEvent(serial, t_fail)` for pool drives failing in June, with the deterministic intra-day offset |
| `policy.RiskTier`, `policy.RiskTierClassifier` | LOW / MEDIUM / HIGH from the two validation-derived boundaries |
| `policy.CheckpointPolicy` (interface) | `long intervalSeconds(RiskTier tier)`, `boolean enabled()` |
| `policy.NoCheckpointPolicy`, `FixedIntervalPolicy`, `RiskAdaptivePolicy`, `YoungDalyAdaptivePolicy`, `OraclePolicy` | Interval rules (§6.2, §9.3). The oracle is the only class allowed failure times, and is used only as an upper bound |
| `sim.DriveHost` (extends `Host`) | Carries serial, timeline and failed flag |
| `sim.FailureInjector` (extends `SimEntity`) | Schedules `HOST_FAILURE` events from `FailureEvent`s; the only consumer of failure dates |
| `sim.CheckpointingBroker` (extends `DatacenterBroker`) | Runs work streams; checkpoint timers, pause/resume, `RISK_UPDATE` handling, failure handling (cancel → lost work → recovery → resubmit), deadlines |
| `sim.WorkStream`, `sim.JobState` | Per-stream job list; per-job progress: L, committed W_c, n, failures, timestamps |
| `sim.SparePool` | Allocates replacement hosts and VMs after failures |
| `sim.CkptTags` | Custom event tags: `HOST_FAILURE`, `CHECKPOINT_DUE`, `CHECKPOINT_DONE`, `RISK_UPDATE`, `RECOVERY_READY` |
| `metrics.MetricsCollector`, `metrics.ResultsWriter` | Per-job and per-failure records; summary CSV/JSON per policy and shard |
| `ExperimentRunner` (main) | For each shard and policy: build datacenter, hosts, spares, broker and injector, run, write results; then aggregate |
| `test/ScenarioTests` | Small hand-computed cases: one job, a known failure time, known C/R/D/B, with lost work and finish time checked exactly per policy |

**Python helper, outside the ML pipeline:** `project/cloudsim/prep/make_risk_tiers.py`. It reads `calibration_validation.csv` and writes `risk_tiers.json` (boundaries, validation rates, MTBFs, ratios), so the tier settings are reproducible and auditable.

## 12. Implementation sequence and anticipated challenges

### 12.1 Sequence

1. **Decide the CloudSim version** (§1.1). With your approval, download it (and Maven if option B), compile a stock example on JDK 24, and confirm the cloudlet pause/resume/cancel API.
2. Write `make_risk_tiers.py` and generate `risk_tiers.json`.
3. Write the trace loaders and policies, with unit tests for the effectiveness timing and carry-forward rule.
4. Write the broker, failure injector and spare pool, and pass `ScenarioTests` (exact hand-computed results).
5. Pilot on one shard: measure memory and runtime, and check event counts.
6. Full runs: E1, E2, E3 × T₀ sweep × shards; then the sensitivity runs.
7. Aggregation, bootstrap CIs and the report.

### 12.2 Anticipated challenges

| # | Challenge | Mitigation |
|---|---|---|
| 1 | No CloudSim and no build tooling installed | Option A builds with `javac` and a jar; option B needs Maven. Decision needed |
| 2 | No native trace failures or checkpointing | Custom broker and injector (§7, §11); pause/resume, with segment cloudlets as fallback |
| 3 | Scale: 110,848 hosts, ~3 GB memory | Deterministic shards; pilot first |
| 4 | Daily risk scores vs minute-scale checkpoints; unknown failure time within the day | d+1 effectiveness rule; deterministic intra-day offset plus sensitivity runs |
| 5 | **Realistic disk failure rates favour little or no checkpointing** (§6.3) | Multi-day jobs, a T₀ sweep, and honest reporting of when checkpointing is *not* worth it |
| 6 | Scores are not calibrated; tier boundaries drift between validation and June | Tiers, not probabilities; report actual June tier shares |
| 7 | Gaps in the prediction file come from future-dependent filtering (leakage risk) | Carry-forward rule; the simulator never reads `label_primary` |
| 8 | Only 175 failure events | Bootstrap CIs; per-failure reporting; no claims beyond the evidence |
| 9 | Spare-host and graceful-departure assumptions | State them; keep them identical across policies |
| 10 | Disk-to-host abstraction | State it in every results table and in the paper (§3) |
| 11 | Per-row validation predictions were not saved in Phase 2 | Tiers use the saved validation percentiles (P90, P99). Finer tiers would need the internal model re-scored on validation (a new script; needs approval) |

## 13. Decisions needed before implementation

1. **CloudSim version:**
   * A — 3.0.3 jar with `javac` (recommended);
   * B — 6.x / 7G with Maven;
   * C — CloudSim Plus, which is a different framework and not recommended given your instruction.

   Plus permission to download it (and Maven for option B).
2. Approve the defaults: C = R = 300 s, D = 60 s, B = 120 s, the job mix {24, 72, 168 h}, deadline slack 1.5, and the T₀ sweep.
3. Approve the assumptions:
   * spare hosts never fail and use the Medium tier;
   * hosts that leave without a failure record stay up;
   * the 4 June failure events outside the pool are excluded.
4. Approve the primary adaptive rule (Young/Daly ratios anchored at T₀) and the tier boundaries P90 = 0.000234, P99 = 0.001732.
