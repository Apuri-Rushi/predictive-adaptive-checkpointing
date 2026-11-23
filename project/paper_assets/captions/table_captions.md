# Table captions

IEEE style: captions go above tables; every `.tex` file already contains its `\caption` and `\label`.

## Table 1: tab01_dataset

* **Files:** `tables/latex/tab01_dataset.tex`, `tables/csv/tab01_dataset.csv`
* **Label:** `tab:dataset`   **Width:** single column   **Main paper:** yes
* **Caption:** Backblaze Q2 2019 dataset characteristics.
* **Table note:** —

## Table 2: tab02_split

* **Files:** `tables/latex/tab02_split.tex`, `tables/csv/tab02_split.csv`
* **Label:** `tab:split`   **Width:** full (table*)   **Main paper:** supplementary / optional
* **Caption:** Preprocessing and chronological split (7-day horizon).
* **Table note:** Positive: the drive records a failure on day t+1 … t+7. Primary negative: the drive is still observed on or after t+7; rows with shorter follow-up are excluded (censored). 5 drives with data-quality problems are excluded. Failure-day rows are not examples. Internal validation for model selection used 2019-04-01 – 05-03 (fit), 05-04 – 05-10 (purge), 05-11 – 05-24 (validation), all inside the training period.

## Table 3: tab03_rf_config

* **Files:** `tables/latex/tab03_rf_config.tex`, `tables/csv/tab03_rf_config.csv`
* **Label:** `tab:rf_config`   **Width:** single column   **Main paper:** supplementary / optional
* **Caption:** Random Forest model configuration.
* **Table note:** —

## Table 4: tab04_rf_performance

* **Files:** `tables/latex/tab04_rf_performance.tex`, `tables/csv/tab04_rf_performance.csv`
* **Label:** `tab:rf_performance`   **Width:** single column   **Main paper:** yes
* **Caption:** Random Forest predictive performance (7-day horizon).
* **Table note:** Validation: 2019-05-11 – 05-24 (internal-validation model, used to choose hyper-parameters and the threshold 0.01368). Test: June 1 – 23, evaluated once with the final model. Row level: each drive-day is one prediction. Drive level: a failed drive counts as detected if it has at least one alarm in its 7-day pre-failure window. A random ranking has PR-AUC equal to the prevalence.

## Table 5: tab05_tiers

* **Files:** `tables/latex/tab05_tiers.tex`, `tables/csv/tab05_tiers.csv`
* **Label:** `tab:tiers`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Risk tiers and adaptive checkpoint-interval rules (E3).
* **Table note:** p is the prior-corrected 7-day failure score. Boundaries are the P90 (0.000234) and P99 (0.001732) of internal-validation scores (May 11 – 24) and were not tuned on June data. The score of day d sets the tier from 00:00 of day d+1 (carried forward if missing; MEDIUM before any score and on spare hosts). E2 uses τ = T0 for every tier; E1 never checkpoints. Design share = intended share on validation; June share = observed share of host-days.

## Table 6: tab06_cloudsim_config

* **Files:** `tables/latex/tab06_cloudsim_config.tex`, `tables/csv/tab06_cloudsim_config.csv`
* **Label:** `tab:cloudsim_config`   **Width:** single column   **Main paper:** yes
* **Caption:** CloudSim simulation configuration.
* **Table note:** —

## Table 7: tab07_workload

* **Files:** `tables/latex/tab07_workload.tex`, `tables/csv/tab07_workload.csv`
* **Label:** `tab:workload`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Workload model and experimental scenarios.
* **Table note:** Job counts differ between scenarios because ρ changes the submit spacing; raw totals are therefore not compared across scenarios.

## Table 8: tab08_policy_rho09

* **Files:** `tables/latex/tab08_policy_rho09.tex`, `tables/csv/tab08_policy_rho09.csv`
* **Label:** `tab:policy_rho09`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Overall policy comparison, ρ = 0.9 (primary).
* **Table note:** ρ = 0.9, all 110,848 hosts, 1,141,653 jobs, 175 failures. Miss % = late jobs / jobs. Lost = computation lost to failures. Overhead = 300 s × completed checkpoint writes (writes cut short by a failure are counted in Waste). Ovh. % and Waste % are percentages of useful compute (sum of job lengths); Waste = overhead + lost + interrupted writes + recovery. Queue = mean waiting time before a job starts. Lost-work CIs: paired host-clustered bootstrap (B = 2,000).

## Table 9: tab09_paired_rho09

* **Files:** `tables/latex/tab09_paired_rho09.tex`, `tables/csv/tab09_paired_rho09.csv`
* **Label:** `tab:paired_rho09`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Paired E3 − E2 comparison at equal T0, ρ = 0.9, all hosts.
* **Table note:** Paired within ρ = 0.9: E2 and E3 at the same T0 run the identical workload, failures and risk trace. Δ = E3 − E2; lower is favourable for every metric. Δ % = Δ / E2 (given only for totals; deadline and queue differences are absolute, in percentage points or h/job). 95 % CI: paired host-clustered Poisson bootstrap (B = 2,000, seed 20190601) on the difference; shards are not treated as samples. Intervals are not adjusted for multiple comparisons and are descriptive only; no significance is claimed. Lost-work intervals rest on 175 failure events and are wide.

## Table 10: tab10_policy_rho10

* **Files:** `tables/latex/tab10_policy_rho10.tex`, `tables/csv/tab10_policy_rho10.csv`
* **Label:** `tab:policy_rho10`   **Width:** full (table*)   **Main paper:** supplementary / optional
* **Caption:** Overall policy comparison, ρ = 1.0 (saturated sensitivity).
* **Table note:** ρ = 1.0, all 110,848 hosts, 1,259,916 jobs, 175 failures. Miss % = late jobs / jobs. Lost = computation lost to failures. Overhead = 300 s × completed checkpoint writes (writes cut short by a failure are counted in Waste). Ovh. % and Waste % are percentages of useful compute (sum of job lengths); Waste = overhead + lost + interrupted writes + recovery. Queue = mean waiting time before a job starts. Lost-work CIs: paired host-clustered bootstrap (B = 2,000).

## Table 11: tab11_paired_rho10

* **Files:** `tables/latex/tab11_paired_rho10.tex`, `tables/csv/tab11_paired_rho10.csv`
* **Label:** `tab:paired_rho10`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Paired E3 − E2 comparison at equal T0, ρ = 1.0, all hosts.
* **Table note:** Paired within ρ = 1.0: E2 and E3 at the same T0 run the identical workload, failures and risk trace. Δ = E3 − E2; lower is favourable for every metric. Δ % = Δ / E2 (given only for totals; deadline and queue differences are absolute, in percentage points or h/job). 95 % CI: paired host-clustered Poisson bootstrap (B = 2,000, seed 20190601) on the difference; shards are not treated as samples. Intervals are not adjusted for multiple comparisons and are descriptive only; no significance is claimed. Lost-work intervals rest on 175 failure events and are wide.

## Table 12: tab12_failing_nonfailing_rho09

* **Files:** `tables/latex/tab12_failing_nonfailing_rho09.tex`, `tables/csv/tab12_failing_nonfailing_rho09.csv`
* **Label:** `tab:strata_rho09`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Failing versus non-failing hosts, ρ = 0.9.
* **Table note:** ρ = 0.9. Failing hosts: the 175 hosts whose drive failed in June (one failure each); non-failing: 110,673 hosts. Non-failing hosts lose no work by construction. CI: host-clustered bootstrap within the stratum.

## Table 12b: tab12b_failing_nonfailing_rho10

* **Files:** `tables/latex/tab12b_failing_nonfailing_rho10.tex`, `tables/csv/tab12b_failing_nonfailing_rho10.csv`
* **Label:** `tab:strata_rho10`   **Width:** full (table*)   **Main paper:** supplementary / optional
* **Caption:** Failing versus non-failing hosts, ρ = 1.0.
* **Table note:** ρ = 1.0. Failing hosts: the 175 hosts whose drive failed in June (one failure each); non-failing: 110,673 hosts. Non-failing hosts lose no work by construction. CI: host-clustered bootstrap within the stratum.

## Table 13: tab13_tier_occupancy

* **Files:** `tables/latex/tab13_tier_occupancy.tex`, `tables/csv/tab13_tier_occupancy.csv`
* **Label:** `tab:tier_occupancy`   **Width:** full (table*)   **Main paper:** yes
* **Caption:** Risk-tier occupancy and failure distribution (June 2019).
* **Table note:** Host-day shares cover June days 1 – 30 and are identical in both scenarios (the risk trace does not depend on ρ). The design target is the share implied by the P90 / P99 validation boundaries. Failures by tier are identical in all 11 policies and both ρ values.

## Table 14: tab14_lost_by_tier_rho09

* **Files:** `tables/latex/tab14_lost_by_tier_rho09.tex`, `tables/csv/tab14_lost_by_tier_rho09.csv`
* **Label:** `tab:lost_tier_rho09`   **Width:** single column   **Main paper:** supplementary / optional
* **Caption:** Lost computation by risk tier at failure, ρ = 0.9.
* **Table note:** ρ = 0.9. Lost computation (h) grouped by the risk tier in force at the failure instant (LOW n = 27, MEDIUM n = 38, HIGH n = 110 failures). Row totals equal the lost-work totals of the overall comparison. Point estimates only; with 27 – 110 failures per tier, differences are uncertain.

## Table 14b: tab14b_lost_by_tier_rho10

* **Files:** `tables/latex/tab14b_lost_by_tier_rho10.tex`, `tables/csv/tab14b_lost_by_tier_rho10.csv`
* **Label:** `tab:lost_tier_rho10`   **Width:** single column   **Main paper:** supplementary / optional
* **Caption:** Lost computation by risk tier at failure, ρ = 1.0.
* **Table note:** ρ = 1.0. Lost computation (h) grouped by the risk tier in force at the failure instant (LOW n = 27, MEDIUM n = 38, HIGH n = 110 failures). Row totals equal the lost-work totals of the overall comparison. Point estimates only; with 27 – 110 failures per tier, differences are uncertain.

## Table 15: tab15_execution_validation

* **Files:** `tables/latex/tab15_execution_validation.tex`, `tables/csv/tab15_execution_validation.csv`
* **Label:** `tab:execution`   **Width:** single column   **Main paper:** yes
* **Caption:** Experiment execution and validation summary.
* **Table note:** Checks (validate_full.py, independent Python recomputation): output hashes, host membership, score timing without look-ahead and carry-forward, failure times, workload regeneration, identical job set in all 11 policies, overhead, recovery timing, lost work, replacement hosts, deadlines, completion, FIFO order and per-job time accounting. Two validator defects (not simulator defects) were fixed before the final validation; simulator outputs were unchanged.
