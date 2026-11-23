# Figure captions

LaTeX-ready captions are in `overleaf/captions_figures.tex` (one `\newcommand` per figure); this file is the readable version.
Width: `col` = single column (`figure`, `\columnwidth`), `dbl` = full width (`figure*`, `\textwidth`).

## fig01_system_architecture

* **File:** `architecture/fig01_system_architecture.{pdf,svg,png}`  (Overleaf: `figures/fig01_system_architecture.pdf`)
* **Label:** `fig:system_architecture`   **Width:** dbl   **Recommended placement:** Sec. III (Proposed system), first figure   **Main paper:** yes
* **Caption:** Overall architecture of the proposed system. The offline pipeline (top) trains a Random Forest on Backblaze SMART data (1 April – 24 May 2019) and writes one prior-corrected 7-day failure score per drive-day for 1–23 June. Only these scores enter the trace-driven CloudSim simulation (bottom), where a risk classifier and an adaptive checkpoint scheduler set each host's checkpoint interval. Failure times come from a separate trace that only the failure injector reads; failure labels are never passed to the simulator. Orange borders: custom components; grey: native CloudSim.
* **Demonstrates:** Separation of offline ML training from online simulation, and the single interface (daily scores) between them.

## fig02_ml_pipeline

* **File:** `architecture/fig02_ml_pipeline.{pdf,svg,png}`  (Overleaf: `figures/fig02_ml_pipeline.pdf`)
* **Label:** `fig:ml_pipeline`   **Width:** col   **Recommended placement:** Sec. III-A (Failure prediction)   **Main paper:** yes
* **Caption:** Random Forest prediction pipeline. Steps 1–8 run offline; step 9 (risk classification) is applied inside the simulator. Labels use a 7-day horizon: a drive-day is positive if the drive records a failure on day t+1 to t+7. The tier boundaries are the 90th and 99th percentiles of validation scores and were not tuned on test data.
* **Demonstrates:** Exact preprocessing, labelling, split, sampling, training, prior correction and tiering steps with their parameters.

## fig03_adaptive_checkpointing

* **File:** `architecture/fig03_adaptive_checkpointing.{pdf,svg,png}`  (Overleaf: `figures/fig03_adaptive_checkpointing.pdf`)
* **Label:** `fig:adaptive`   **Width:** col   **Recommended placement:** Sec. III-B (Adaptive checkpoint scheduling)   **Main paper:** yes
* **Caption:** Adaptive checkpoint scheduling (policy E3). The Random Forest supplies only a risk score. A fixed classifier maps the score to a tier, and the scheduler maps the tier to a checkpoint interval τ relative to the baseline T0. The table lists the resulting intervals for each T0; the fixed policy E2 uses τ = T0 for every tier.
* **Demonstrates:** That the RF predicts risk, not intervals; the exact tier-to-interval rules (2.65T0, T0, T0/4.9).

## fig04_cloudsim_integration

* **File:** `architecture/fig04_cloudsim_integration.{pdf,svg,png}`  (Overleaf: `figures/fig04_cloudsim_integration.pdf`)
* **Label:** `fig:cloudsim`   **Width:** dbl   **Recommended placement:** Sec. III-C (CloudSim integration)   **Main paper:** yes
* **Caption:** CloudSim integration and recovery architecture. Native CloudSim 3.0.3 entities (grey) are used unmodified. The custom broker runs each job as a chain of compute-segment cloudlets and writes each checkpoint as a 300 s cloudlet. On a host failure it moves the job to a spare host and restores from the last completed checkpoint. Each Backblaze drive is modelled as one host, and a recorded disk failure is treated as a host failure; this is a modelling assumption.
* **Demonstrates:** Which parts are custom versus native CloudSim; how checkpoint state, failure injection, spare hosts and recovery are realised.

## fig05_execution_flow

* **File:** `architecture/fig05_execution_flow.{pdf,svg,png}`  (Overleaf: `figures/fig05_execution_flow.pdf`)
* **Label:** `fig:execution_flow`   **Width:** dbl   **Recommended placement:** Sec. III-C, after Fig. cloudsim   **Main paper:** yes
* **Caption:** End-to-end execution flow for one job. A job runs in compute segments that end at the next checkpoint due time, at midnight (when the daily risk tier may change) or at job end. A host failure interrupts the running segment or checkpoint write. The job then resumes on a spare host after D + B = 180 s: from its last completed checkpoint after a 300 s restore, or from zero if no checkpoint exists.
* **Demonstrates:** The runtime decision logic: tier lookup, interval selection, checkpoint commit, failure handling, restore vs restart.

## fig06_experimental_design

* **File:** `architecture/fig06_experimental_design.{pdf,svg,png}`  (Overleaf: `figures/fig06_experimental_design.pdf`)
* **Label:** `fig:experimental_design`   **Width:** dbl   **Recommended placement:** Sec. IV (Experimental setup)   **Main paper:** yes
* **Caption:** Experimental design. In each scenario, all 11 policy configurations (E1, plus E2 and E3 at five baseline intervals T0) run on all 56 shards with the identical workload, failure trace and risk trace, so comparisons are paired. The two load scenarios (ρ = 0.9 primary, ρ = 1.0 saturated sensitivity) have different workloads and are analysed separately.
* **Demonstrates:** Common inputs, the 11 policy runs, collected metrics and the paired statistical comparison; scenario separation.

## g01_rf_roc_curve

* **File:** `graphs/random_forest/g01_rf_roc_curve.{pdf,svg,png}`  (Overleaf: `figures/g01_rf_roc_curve.pdf`)
* **Label:** `fig:rf_roc`   **Width:** col   **Recommended placement:** Sec. V-A (Prediction results)   **Main paper:** yes
* **Caption:** ROC curve of the Random Forest on the 1–23 June test set (2,544,754 drive-days, 997 positives). (a) Full curve, AUC = 0.804. (b) The same curve with a logarithmic FPR axis; markers show recall at 0.1 % FPR (16.0 %) and 1 % FPR (37.3 %).
* **Demonstrates:** Discrimination over the whole range and in the low-FPR region that matters operationally.

## g02_rf_precision_recall_curve

* **File:** `graphs/random_forest/g02_rf_precision_recall_curve.{pdf,svg,png}`  (Overleaf: `figures/g02_rf_precision_recall_curve.pdf`)
* **Label:** `fig:rf_pr`   **Width:** col   **Recommended placement:** Sec. V-A   **Main paper:** yes
* **Caption:** Precision–recall curve on the June test set (PR-AUC = 0.0337, about 86 times the 0.039 % prevalence; log-scaled precision axis). The marker shows the alarm threshold 0.01368 chosen by maximum F1 on validation: precision 4.3 %, recall 20.7 %.
* **Demonstrates:** Performance under extreme class imbalance; the operating point used for alarms.

## g03_rf_confusion_matrix

* **File:** `graphs/random_forest/g03_rf_confusion_matrix.{pdf,svg,png}`  (Overleaf: `figures/g03_rf_confusion_matrix.pdf`)
* **Label:** `fig:rf_cm`   **Width:** col   **Recommended placement:** Sec. V-A   **Main paper:** supplementary / optional
* **Caption:** Confusion matrix on the June test set at the validation-selected threshold (p ≥ 0.01368). Shading shows the row-normalised rate. The model raises 4,597 false alarms for 206 true positives and misses 79 % of positive drive-days.
* **Demonstrates:** The concrete error counts behind the precision/recall figures.

## g04_rf_score_distribution

* **File:** `graphs/random_forest/g04_rf_score_distribution.{pdf,svg,png}`  (Overleaf: `figures/g04_rf_score_distribution.pdf`)
* **Label:** `fig:rf_scores`   **Width:** col   **Recommended placement:** Sec. V-A or V-D (tiers)   **Main paper:** supplementary / optional
* **Caption:** Distribution of prior-corrected scores (log scale) for June drive-days with and without a failure in the next 7 days, each normalised to 100 %. Dotted lines mark the tier boundaries (0.000234, 0.001732) and the alarm threshold (0.01368). The two classes overlap substantially.
* **Demonstrates:** Score separation between classes and where the fixed tier boundaries cut the June distribution.

## g05_rf_feature_importance

* **File:** `graphs/random_forest/g05_rf_feature_importance.{pdf,svg,png}`  (Overleaf: `figures/g05_rf_feature_importance.pdf`)
* **Label:** `fig:rf_importance`   **Width:** dbl   **Recommended placement:** Sec. V-A   **Main paper:** supplementary / optional
* **Caption:** Top 15 features. (a) Mean decrease in impurity, final model. (b) Permutation importance (mean decrease in average precision ± s.d.) of the internal-validation model on a validation subsample. Reallocated-sector counts (SMART 5) dominate both rankings. Correlated features share importance, so the rankings should be read in groups.
* **Demonstrates:** Which SMART attributes and temporal transformations drive the predictions.

## g06_overhead_vs_T0_rho09

* **File:** `graphs/checkpointing_primary/g06_overhead_vs_T0_rho09.{pdf,svg,png}`  (Overleaf: `figures/g06_overhead_vs_T0_rho09.pdf`)
* **Label:** `fig:overhead_rho09`   **Width:** col   **Recommended placement:** Sec. V-B (Primary results)   **Main paper:** supplementary / optional
* **Caption:** Checkpoint overhead as a percentage of useful computation for fixed (E2) and RF-adaptive (E3) checkpointing at each baseline interval T0, ρ = 0.9, all hosts (log scale; E1 has no overhead). Whiskers are 95 % host-clustered bootstrap CIs and are very narrow. E3 is lower at T0 ≤ 12 h and higher at 24–72 h.
* **Demonstrates:** Overhead cost of each policy across baselines.

## g07_lost_work_vs_T0_rho09

* **File:** `graphs/checkpointing_primary/g07_lost_work_vs_T0_rho09.{pdf,svg,png}`  (Overleaf: `figures/g07_lost_work_vs_T0_rho09.pdf`)
* **Label:** `fig:lost_rho09`   **Width:** col   **Recommended placement:** Sec. V-B   **Main paper:** supplementary / optional
* **Caption:** Lost computation caused by the 175 host failures, ρ = 0.9 (log scale). The dashed line shows no checkpointing (E1, 8,375 h). Whiskers are 95 % bootstrap CIs; they are wide because they rest on 175 failure events.
* **Demonstrates:** Protection against lost work for each policy and baseline.

## g08_deadline_miss_vs_T0_rho09

* **File:** `graphs/checkpointing_primary/g08_deadline_miss_vs_T0_rho09.{pdf,svg,png}`  (Overleaf: `figures/g08_deadline_miss_vs_T0_rho09.pdf`)
* **Label:** `fig:deadline_rho09`   **Width:** dbl   **Recommended placement:** Sec. V-B   **Main paper:** yes
* **Caption:** Deadline miss rate, ρ = 0.9. (a) All hosts: only E3 at T0 = 1 h misses an appreciable share (4.54 %). Every other E2/E3 configuration misses at most 0.015 %; value labels below 0.05 % are omitted. (b) The 175 failing hosts: E1 misses 19.8 %, and E3 at 1 h misses 23.3 %. Whiskers are 95 % bootstrap CIs.
* **Demonstrates:** Deadline impact overall and on the hosts that fail (negative result for E3 at 1 h shown).

## g09_wasted_time_all_policies_rho09

* **File:** `graphs/checkpointing_primary/g09_wasted_time_all_policies_rho09.{pdf,svg,png}`  (Overleaf: `figures/g09_wasted_time_all_policies_rho09.pdf`)
* **Label:** `fig:wasted_rho09`   **Width:** col   **Recommended placement:** Sec. V-B   **Main paper:** supplementary / optional
* **Caption:** Total wasted time (checkpoint overhead + lost work + interrupted checkpoint writes + recovery) as a percentage of useful computation, ρ = 0.9 (log scale). No checkpointing (E1) wastes the least overall (0.011 %). At these failure rates, checkpointing pays off by protecting the jobs that failures hit (Fig. [fig:deadline_rho09]b), not in aggregate efficiency.
* **Demonstrates:** Aggregate efficiency of all 11 configurations, including the unfavourable comparison with E1.

## g10_overhead_vs_lost_tradeoff_rho09

* **File:** `graphs/checkpointing_primary/g10_overhead_vs_lost_tradeoff_rho09.{pdf,svg,png}`  (Overleaf: `figures/g10_overhead_vs_lost_tradeoff_rho09.pdf`)
* **Label:** `fig:tradeoff_rho09`   **Width:** col   **Recommended placement:** Sec. V-B   **Main paper:** yes
* **Caption:** Trade-off between overhead and lost computation, ρ = 0.9 (log–log). Each point is one policy at one T0; labels are on the E2 points, and the E3 point for the same T0 lies just below. E3 is lower on both axes at T0 ≤ 12 h; the 1 h point carries a deadline penalty (Fig. [fig:deadline_rho09]). At 24 and 72 h, E3 trades higher overhead for lower lost work. Whiskers: 95 % CIs of lost work.
* **Demonstrates:** Whether E3 shifts the overhead/lost-work frontier relative to E2.

## g11_checkpoints_per_job_rho09

* **File:** `graphs/checkpointing_primary/g11_checkpoints_per_job_rho09.{pdf,svg,png}`  (Overleaf: `figures/g11_checkpoints_per_job_rho09.pdf`)
* **Label:** `fig:ckpts_rho09`   **Width:** col   **Recommended placement:** Sec. V-B   **Main paper:** supplementary / optional
* **Caption:** Mean checkpoints per job, ρ = 0.9 (log scale). E3 writes fewer checkpoints than E2 at T0 ≤ 12 h, because 54 % of June host-days are LOW, and more at 24–72 h.
* **Demonstrates:** Checkpoint frequency underlying the overhead differences.

## g12_paired_E3_vs_E2_rho09

* **File:** `graphs/checkpointing_primary/g12_paired_E3_vs_E2_rho09.{pdf,svg,png}`  (Overleaf: `figures/g12_paired_E3_vs_E2_rho09.pdf`)
* **Label:** `fig:paired_rho09`   **Width:** dbl   **Recommended placement:** Sec. V-B (statistical comparison)   **Main paper:** yes
* **Caption:** Paired E3 − E2 differences at equal T0, ρ = 0.9, all hosts: (a)–(c) relative to E2, (d) in percentage points. Intervals are 95 % host-clustered bootstrap CIs of the difference, rescaled by the E2 point estimate in (a)–(c). Filled markers: the interval excludes 0. Negative values favour E3. The intervals are not adjusted for multiple comparisons, and no significance is claimed.
* **Demonstrates:** Direction, size and uncertainty of every primary E3-vs-E2 effect in one view.

## g12_paired_E3_vs_E2_rho10

* **File:** `graphs/saturated_sensitivity/g12_paired_E3_vs_E2_rho10.{pdf,svg,png}`  (Overleaf: `figures/g12_paired_E3_vs_E2_rho10.pdf`)
* **Label:** `fig:paired_rho10`   **Width:** dbl   **Recommended placement:** Sec. V-C (Saturated sensitivity)   **Main paper:** supplementary / optional
* **Caption:** Paired E3 − E2 differences at equal T0 under saturation, ρ = 1.0, all hosts. The format is the same as Fig. [fig:paired_rho09]. This experiment has a different workload from ρ = 0.9, so its effects are compared only in direction and size.
* **Demonstrates:** Whether the primary effects persist without idle slack.

## g13_deadline_miss_vs_T0_rho10

* **File:** `graphs/saturated_sensitivity/g13_deadline_miss_vs_T0_rho10.{pdf,svg,png}`  (Overleaf: `figures/g13_deadline_miss_vs_T0_rho10.pdf`)
* **Label:** `fig:deadline_rho10`   **Width:** col   **Recommended placement:** Sec. V-C   **Main paper:** supplementary / optional
* **Caption:** Deadline miss rate under saturation, ρ = 1.0, all hosts. Without slack, checkpoint overhead becomes queueing delay: at T0 = 1 h, E2 misses 50.7 % of deadlines and E3 34.2 %; at 4 h, 7.6 % versus 3.2 %. At 12 h, E3 is worse (0.27 % versus 0.01 %).
* **Demonstrates:** Deadline sensitivity to saturation, including the unfavourable 12 h result.

## g14_queueing_vs_T0_rho10

* **File:** `graphs/saturated_sensitivity/g14_queueing_vs_T0_rho10.{pdf,svg,png}`  (Overleaf: `figures/g14_queueing_vs_T0_rho10.pdf`)
* **Label:** `fig:queue_rho10`   **Width:** col   **Recommended placement:** Sec. V-C   **Main paper:** supplementary / optional
* **Caption:** Mean queueing delay per job, ρ = 1.0 (log scale). E3 reduces queueing at every T0. The dashed line shows E1 (0.04 h).
* **Demonstrates:** How overhead turns into queueing delay under saturation.

## g15_lost_work_vs_T0_rho10

* **File:** `graphs/saturated_sensitivity/g15_lost_work_vs_T0_rho10.{pdf,svg,png}`  (Overleaf: `figures/g15_lost_work_vs_T0_rho10.pdf`)
* **Label:** `fig:lost_rho10`   **Width:** col   **Recommended placement:** Sec. V-C   **Main paper:** supplementary / optional
* **Caption:** Lost computation, ρ = 1.0 (log scale), with 95 % bootstrap CIs. The dashed line shows E1 (9,603 h).
* **Demonstrates:** Lost-work protection under saturation.

## g16_failing_host_deadline_miss_both_rho

* **File:** `graphs/saturated_sensitivity/g16_failing_host_deadline_miss_both_rho.{pdf,svg,png}`  (Overleaf: `figures/g16_failing_host_deadline_miss_both_rho.pdf`)
* **Label:** `fig:failing_deadline`   **Width:** dbl   **Recommended placement:** Sec. V-C   **Main paper:** yes
* **Caption:** Deadline miss rate on the 175 failing hosts, fixed (E2) versus adaptive (E3): (a) ρ = 0.9, (b) ρ = 1.0. Under saturation, E3's extra checkpoints on HIGH-tier hosts raise failing-host deadline misses at T0 ≤ 4 h (25.5 % versus 14.9 % at 4 h), even though lost work falls. The two panels are separate experiments with different workloads.
* **Demonstrates:** The main negative finding: the saturation penalty on the hosts E3 is meant to protect.

## g17_tier_occupancy

* **File:** `graphs/risk_analysis/g17_tier_occupancy.{pdf,svg,png}`  (Overleaf: `figures/g17_tier_occupancy.pdf`)
* **Label:** `fig:tier_occupancy`   **Width:** col   **Recommended placement:** Sec. V-D (Risk tiers and distribution shift)   **Main paper:** yes
* **Caption:** Share of June host-days in each risk tier, compared with the validation design target (90/9/1 %). June scores are shifted upward: only 54.1 % of host-days are LOW, and 6.6 % are HIGH. Failing hosts spend 52.3 % of their host-days in HIGH.
* **Demonstrates:** Distribution shift between validation and June, and that the ranking still separates failing hosts.

## g18_failures_by_tier

* **File:** `graphs/risk_analysis/g18_failures_by_tier.{pdf,svg,png}`  (Overleaf: `figures/g18_failures_by_tier.pdf`)
* **Label:** `fig:failures_tier`   **Width:** col   **Recommended placement:** Sec. V-D   **Main paper:** supplementary / optional
* **Caption:** Risk tier in force at the instant of each of the 175 failures, identical across policies and scenarios: 110 HIGH, 38 MEDIUM and 27 LOW.
* **Demonstrates:** How often the predictor had the failing host in the right tier at failure time.

## g19_lost_work_by_tier_rho09

* **File:** `graphs/risk_analysis/g19_lost_work_by_tier_rho09.{pdf,svg,png}`  (Overleaf: `figures/g19_lost_work_by_tier_rho09.pdf`)
* **Label:** `fig:lost_tier_rho09`   **Width:** dbl   **Recommended placement:** Sec. V-D   **Main paper:** yes
* **Caption:** Lost computation grouped by the tier in force at failure, ρ = 0.9 (log scale; point estimates). E3 sharply reduces lost work for failures in HIGH and has little effect in MEDIUM. It increases lost work for the 27 failures the model ranked LOW, where its interval is 2.65 T0.
* **Demonstrates:** Where the adaptive policy helps (model right) and hurts (model wrong).

## g20_overhead_by_tier_rho09

* **File:** `graphs/risk_analysis/g20_overhead_by_tier_rho09.{pdf,svg,png}`  (Overleaf: `figures/g20_overhead_by_tier_rho09.pdf`)
* **Label:** `fig:overhead_tier_rho09`   **Width:** col   **Recommended placement:** Sec. V-D   **Main paper:** supplementary / optional
* **Caption:** Checkpoint overhead split by the tier in force when each checkpoint was written, ρ = 0.9, all hosts, indexed to the E2 total at the same T0 (= 100). E3 cuts LOW-tier overhead and spends much of the saving on HIGH-tier checkpoints. At T0 = 72 h the LOW interval (190.8 h) exceeds the longest job (168 h), so E3 writes almost no LOW-tier checkpoints (0.2 % of its checkpoints).
* **Demonstrates:** Where the overhead budget goes; the cost of the distribution shift on healthy HIGH-tier hosts.
