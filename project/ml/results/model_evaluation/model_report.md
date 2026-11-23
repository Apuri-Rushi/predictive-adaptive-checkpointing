# Model Report — Baseline Random Forest, 7-Day Disk-Failure Prediction (Backblaze Q2 2019)

**Phase 2 baseline.** The dataset, labels, features and validation rules from Phase 1 are used unchanged. CloudSim has not been touched.

Every number in this report comes from the files in `project/ml/results/model_evaluation/`. They are produced by:

```
python -I project/ml/training/train_random_forest.py
```

The run took 768 s and peaked at about 1.18 GB of memory (sampled at log points).

---

## 1. What the model predicts

For a hard drive observed on day *t*, the model outputs:

> **p = P(the drive records a failure on one of days t+1 … t+7 | its SMART history up to and including day t)**

* It is a **7-day risk score for a drive**. It does **not** predict the exact day of failure, and it says nothing directly about a host or VM.
* The score is a prior-corrected probability (§5). Treat it as a ranking of risk with rough probability scale, not as a calibrated probability (§7.3).

## 2. Input features

The model uses the **128 approved features** from `project/ml/processed/feature_manifest.md`, in the order saved in `project/ml/models/feature_order.txt`. All are built only from records dated **≤ t**.

| Group | Count | What it captures |
|---|---|---|
| Current raw SMART value, for 20 attributes | 20 | Current drive state. Core attributes: 1, 3, 4, 5, 7, 9, 10, 12, 192, 193, 194, 197, 198, 199. Partial attributes: 187, 188, 190, 240, 241, 242 |
| Previous day's value (`_prev1`) | 20 | Short-term memory |
| 1-day and 7-day change (`_diff1`, `_diff7`) | 40 | Degradation speed, e.g. growth in reallocated sectors |
| 7-day mean and std (`_mean7`, `_std7`) | 40 | Recent level and instability |
| "Not reported" flags for 187, 188, 190, 240, 241, 242 | 6 | Whether the drive model reports that attribute |
| `n_obs_prev7`, `history_complete_7d` | 2 | How much history is available |

* Missing values stay **NaN**; scikit-learn 1.7.2's Random Forest routes them natively.
* **Not used as features:** `serial_number`, `date`, `failure`, `source_file_altered`, `capacity_bytes`, `model`, `fold`. This is checked by an assertion in `rf_config.py`.

## 3. Training-sample preparation  (`sampling.py`, `sampling_summary.json`)

| Item | Value |
|---|---|
| Source | `train_chronological.csv.gz`: 5,745,061 rows, observation dates 2019-04-01 … 05-24 |
| Positives | **All 1,842** kept (305 drives) |
| Negatives | **36,840 of 5,743,219** sampled, so exactly 20 : 1 |
| How negatives were allocated | Quota spread over 2,099 (date × drive model) groups in proportion to their size, using largest-remainder rounding. 1,127 small groups received 0 rows |
| How rows were chosen within a group | The rows with the smallest `crc32("20190401|serial|date")`, ties broken by file order |
| Seed | `20190401` |
| Distribution preserved | Largest difference in negative share: by date 0.006 percentage points, by drive model 0.085 percentage points (`sampling_distribution_by_*.csv`) |
| Memory | Two streaming passes (light columns first, then extraction). The whole file is never loaded |
| Test data | **Not downsampled.** All 2,544,754 June rows were scored |

## 4. Handling class imbalance and choosing the model

* **Imbalance** is handled only through the 20 : 1 negative sampling. No class weights are used, so the prior correction in §5 is exact in form.
* **Internal time-based validation** (`rf_config.py`), entirely inside the training period:

  | Part | Dates | Use |
  |---|---|---|
  | Fit | 04-01 … 05-03 | Sampled rows: 1,058 positives and 22,337 negatives |
  | Purge | 05-04 … 05-10 | Not used. It ensures no fit label window reaches the validation dates |
  | Validation | 05-11 … 05-24 | **All** 1,508,766 rows at the natural ratio: 481 positives from 107 drives |

* **Grid** (`validation_grid_results.csv`): 300 trees, `max_features = "sqrt"`, `max_depth` ∈ {10, 20, unlimited} × `min_samples_leaf` ∈ {1, 5, 20}.
  * Validation PR-AUC ranged from **0.040 to 0.048**. The differences are small compared with the uncertainty from only 107 validation drives.
  * Selected: **`max_depth = 20`, `min_samples_leaf = 1`** (PR-AUC 0.0485).
* **Threshold:** the one with the highest F1 on validation, on the corrected-probability scale: **0.01368** (validation F1 0.135, precision 9.5 %, recall 23.5 %).
* **Final model:** the selected configuration refit on the full training sample (38,682 rows) in 23 s. It is saved as `project/ml/models/random_forest_7d.joblib` (3.8 MB).
* **The June test set was used once**, after everything above was fixed.

## 5. Probability correction  (`metrics.prior_correct`)

* Sampling keeps every positive and a fraction β of the negatives. That multiplies the class odds by 1/β, so a score *s* learned on the sample maps back to the population as:

  > **p = β·s / (β·s + 1 − s)**   (Elkan 2001; Dal Pozzolo et al. 2015)

* **β values:**
  * final model: β = 36,840 / 5,743,219 = **0.006415**. Population prevalence is 3.2 × 10⁻⁴, against 1/21 ≈ 0.048 in the sample;
  * internal validation model: β_fit = 0.006407.
* The correction is **essential**. Uncorrected scores give a test Brier score of 0.0101, versus 0.000387 after correction.
* The formula is exact only if *s* is calibrated on the sampled data, and Random Forest scores usually are not. So calibration is **tested**, not assumed.

## 6. Evaluation results

### 6.1 Row level (each drive-day is one prediction)

| Metric | Validation (May 11–24) | **Test (June 1–23)** |
|---|---|---|
| Rows / positive rows | 1,508,766 / 481 | **2,544,754 / 997** |
| Prevalence | 0.032 % | 0.039 % |
| PR-AUC (a random model scores the prevalence) | 0.0485 | **0.0337** (≈ 86 × prevalence) |
| ROC-AUC | 0.853 | 0.804 |
| Recall at 0.1 % FPR | 27.2 % | **16.0 %** |
| Recall at 1 % FPR | 52.4 % | **37.3 %** |
| Brier score (always predicting the prevalence gives) | 0.000313 (0.000319) | **0.000387** (0.000392) |

Confusion matrix on the test set at threshold 0.01368:

| | Predicted fail | Predicted OK |
|---|---|---|
| **Fails within 7 days** | TP 206 | FN 791 |
| **Does not** | FP 4,597 | TN 2,539,160 |

That gives precision 4.3 %, recall 20.7 % and FPR 0.18 %.

With the sensitivity labels, the results are virtually identical (PR-AUC 0.0337, recall 37.3 % at 1 % FPR).

### 6.2 Drive level (repeated positive rows of one drive are not counted as separate failures)

Failed-drive files: `test_failed_drives.csv` and `validation_failed_drives.csv`.

| Metric | Validation | **Test** |
|---|---|---|
| Failed drives with ≥ 1 positive row in the period | 107 | **175** |
| Detected: ≥ 1 alarm in their 7-day pre-failure window | 37 (34.6 %) | **59 (33.7 %)** |
| Lead time from first alarm to failure | mean 4.3, median 4 days | **mean 4.3, median 4 days** |
| Lead-time distribution, days 1…7 | 5 / 9 / 2 / 3 / 2 / 3 / 13 | **8 / 9 / 8 / 5 / 4 / 9 / 16** |
| False alarms per 1,000 drive-days | 0.71 | **1.81** |
| Never-failed drives with ≥ 1 alarm | 182 of 108,207 (0.17 %) | **1,635 of 110,673 (1.48 %)** |

* A lead time of 7 means the first alarm came on the first day the drive entered its 7-day window.
* **Reading this for operations:** over the 23 June days, the model flagged 59 of the 175 drives that went on to fail. It also flagged 1,635 drives that did not fail, so about 28 flagged healthy drives for every flagged failing one.

Test results by drive model (`test_metrics_by_model.csv`):

| Drive model | Failed drives | PR-AUC | Failed drives detected |
|---|---|---|---|
| ST12000NM0007 | 87 | 0.057 | 47 % |
| ST4000DM000 | 40 | 0.036 | 20 % |
| ST8000NM0055 | 19 | 0.009 | 21 % |

Smaller models have too few failures for reliable per-model figures.

### 6.3 Calibration  (`calibration_validation.csv`, `calibration_test.csv`)

The tables use quantile bins of corrected probability, plus the top 1 % and top 0.1 % of scores.

| Test slice | Mean predicted | Observed rate |
|---|---|---|
| All rows | 0.046 % | 0.039 % |
| Deciles 1–7 | 0.004 – 0.023 % | 0.005 – 0.029 % |
| Deciles 8–9 | 0.038 % / 0.067 % | 0.026 % / 0.023 % (**over-predicts**) |
| Top 10 % | 0.28 % | 0.23 % |
| Top 1 % | 1.07 % | 1.45 % |
| Top 0.1 % | 2.83 % | 6.21 % (**under-predicts about 2×**) |

* On validation, the overall mean is **under**-predicted (0.019 % vs 0.032 %), and the top 0.1 % is predicted at 2.6 % but observed at 8.3 %.
* **Conclusion:** after correction the probabilities are on the right order of magnitude, and they rank risk usefully: the observed failure rate rises about 1,200-fold from the lowest decile (0.005 %) to the top 0.1 % (6.2 %).
* **They are not reliably calibrated.** The Brier score is only 1.3 % better than predicting a constant, the direction of the overall bias changes between periods, and the highest-risk drives are under-estimated about 2×. Do not quote them as exact failure probabilities.

### 6.4 Feature importance  (`feature_importance.csv`)

* **Impurity-based ranking (final model):** dominated by **SMART 5, reallocated sectors**, in its current, previous-day, 7-day change, mean and std forms. Next come **187** (reported uncorrectable errors), **197** (current pending sectors) and **198** (offline uncorrectable sectors).
* **Permutation ranking** (internal model; validation subsample of all 481 positives plus about 1/30 of negatives; average-precision scoring):
  1. `smart_5_raw`
  2. `smart_5_raw_diff7`
  3. `smart_5_raw_std7`
  4. `smart_5_raw_diff1`
  5. `smart_197_raw_mean7`
  6. `smart_187_raw_diff7`
* This matches the known role of sector-reallocation and pending-sector counts in disk failure. The change features (`diff1`, `diff7`) add information beyond the current values.
* Both rankings are biased by correlated features (e.g. `prev1` vs the current value), so read them as groups.

## 7. Interpretation and limitations

1. **Useful but modest discrimination.** At 1 % FPR, 37 % of positive rows are caught. About a third of failing drives get at least one warning, typically 4 days ahead. **About two thirds of failures get no warning at all**; many fail without SMART changes beforehand.
2. **The model does worse on June than on validation.** PR-AUC fell from 0.048 to 0.034, and recall at 1 % FPR from 52 % to 37 %. The threshold also moved: chosen for 0.07 % FPR on validation, it gives 0.18 % FPR on test. Likely causes:
   * a later period, with a different mix of drive models and ages;
   * the final model was refit on more data than the model the threshold was chosen on;
   * the validation set covers only 107 failed drives.

   Expect operating points to drift and re-check them over time.
3. **Calibration is approximate** (§6.3). If the CloudSim scheduler needs true probabilities, a separate calibration step fitted on held-out training-period data, never on June, would be needed. That is a decision for the next phase.
4. **Good row-level metrics do not imply good drive-level detection.** Row metrics count up to 7 correlated rows per failing drive. Section 6.2 is the relevant view for "will this disk fail soon".
5. **Scope:**
   * Three months of data; 305 training and 175 test failing drives.
   * Failures are concentrated in three Seagate models, and performance varies strongly by model.
   * Most drives are left-truncated: 98 % of failed drives were already running on 1 April, and their earlier history is unknown.
   * June 17 has damaged columns set to NaN.
   * This is **disk** failure risk. Treating it as CloudSim host or VM failure risk is a separate modelling assumption.
6. **Baseline only.** The hyperparameter search was deliberately small (9 configurations) and the grid differences are within noise. Further gains would need methodological changes, such as model-aware features, more data or calibration. Those are outside this phase.

## 8. Artifacts

`project/ml/models/`:

| File | Content |
|---|---|
| `random_forest_7d.joblib` | Trained final RandomForestClassifier |
| `random_forest_7d_metadata.json` | Feature order, model parameters, sampling configuration, β values and formula, threshold and rule, validation windows |
| `feature_order.txt` | The 128 features in model order |

`project/ml/results/model_evaluation/`:

| File | Content |
|---|---|
| `sampling_summary.json` | Seed, ratio, counts, per-date population and sampled negatives |
| `sampling_distribution_by_date.csv`, `sampling_distribution_by_model.csv` | Population vs sample shares |
| `validation_grid_results.csv` | All 9 configurations on validation |
| `validation_metrics.json`, `validation_failed_drives.csv` | Selected model: row-level and drive-level validation results |
| `test_metrics.json`, `test_failed_drives.csv`, `test_metrics_by_model.csv` | Final test results |
| `calibration_validation.csv`, `calibration_test.csv` | Reliability tables |
| `feature_importance.csv` | Impurity and permutation importance with ranks |
| `test_predictions.csv.gz` | Per-row June scores (raw and corrected) and labels, for later CloudSim integration |
| `training_log.txt`, `run_stdout.txt`, `run_resources.json` | Logs, runtime and memory |

Source code: `project/ml/training/rf_config.py`, `sampling.py`, `metrics.py`, `train_random_forest.py`.
