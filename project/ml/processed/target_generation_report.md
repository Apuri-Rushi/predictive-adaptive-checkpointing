# Target Generation Report — 7-day disk failure (Backblaze Q2 2019)

Built by `build_dataset.py` in 2343 s; validated by `validate_dataset.py`. **Validation: ALL CHECKS PASSED.**

## Label rules (as approved)

* Observation date t = file-name date. F = file date of the drive's `failure = 1` record.
* Positive: t < F ≤ t+7. Primary negative: no failure in t+1..t+7 and an observation on/after t+7.
* Sensitivity negative: no failure in t+1..t+7 and observations on all of t+1..t+7.
* Excluded: unknown outcome; failure-day and later records; the 5 quality-excluded drives.

## Counts (recounted from the written files) vs methodology

| Split | Count | Built | Methodology | Match |
|---|---|---|---|---|
| train | positive_rows | 1,842 | 1,842 | yes |
| train | positive_drives | 305 | 305 | yes |
| train | negative_rows_primary | 5,743,219 | 5,743,219 | yes |
| train | negative_rows_sensitivity | 5,740,680 | 5,740,680 | yes |
| train | unknown_rows_sensitivity_within_primary_rows | 2,539 | 2,539 | yes |
| test | positive_rows | 997 | 997 | yes |
| test | positive_drives | 175 | 175 | yes |
| test | negative_rows_primary | 2,543,757 | 2,543,757 | yes |
| test | negative_rows_sensitivity | 2,542,168 | 2,542,168 | yes |
| test | unknown_rows_sensitivity_within_primary_rows | 1,589 | 1,589 | yes |

## Written examples

| File | Rows | Positives (drives) | Primary negatives | Sensitivity-eligible rows |
|---|---|---|---|---|
| `train_chronological.csv.gz` | 5,745,061 | 1,842 (305) | 5,743,219 | 5,742,522 |
| `test_chronological.csv.gz` | 2,544,754 | 997 (175) | 2,543,757 | 2,543,165 |

## 2019-06-17 safeguard

* Rows from the altered file written to the test set: 110,524 (45 positives); `source_file_altered = 1`.
* Set to NaN on that day: smart_7_raw, smart_188_raw, smart_240_raw, smart_241_raw, smart_242_raw (non-null before masking: {'smart_7_raw': 110456, 'smart_188_raw': 80816, 'smart_240_raw': 83109, 'smart_241_raw': 81402, 'smart_242_raw': 81402}).
* smart_231_raw, smart_232_raw are damaged too but are not used by the pipeline.
* Derived features whose window includes 2019-06-17 are NaN for these columns (diff1 on 06-18, mean7/std7 on 06-17..06-23).

## Validation assertions

* PASS — feature list matches features.feature_names() (128 features)
* PASS — no identifier/label/date/source-flag/capacity column among features ([])
* PASS — train: columns = metadata + features + labels 
* PASS — test: columns = metadata + features + labels 
* PASS — train: dates within approved window (2019-04-01..2019-05-24)
* PASS — train: no label window crosses into test (max date + 7 < 2019-06-01) (2019-05-31)
* PASS — train: label_primary_invalid == 0 (0)
* PASS — train: pos_with_sens_not_1 == 0 (0)
* PASS — train: fold_mismatch == 0 (0)
* PASS — train: rows_on_or_after_failure == 0 (0)
* PASS — train: pos_outside_1_7 == 0 (0)
* PASS — train: neg_with_failure_within_7 == 0 (0)
* PASS — train: hist_flag_inconsistent == 0 (0)
* PASS — train: diff1_without_both == 0 (0)
* PASS — train: mean7_with_short_history == 0 (0)
* PASS — train: missing_flag_vs_value_mismatch == 0 (0)
* PASS — train: source_flag_wrong == 0 (0)
* PASS — train: june17_masked_non_null == 0 (0)
* PASS — train: june18_diff1_non_null_masked == 0 (0)
* PASS — train: june17_window_mean7_non_null_masked == 0 (0)
* PASS — test: dates within approved window (2019-06-01..2019-06-23)
* PASS — test: label_primary_invalid == 0 (0)
* PASS — test: pos_with_sens_not_1 == 0 (0)
* PASS — test: fold_mismatch == 0 (0)
* PASS — test: rows_on_or_after_failure == 0 (0)
* PASS — test: pos_outside_1_7 == 0 (0)
* PASS — test: neg_with_failure_within_7 == 0 (0)
* PASS — test: hist_flag_inconsistent == 0 (0)
* PASS — test: diff1_without_both == 0 (0)
* PASS — test: mean7_with_short_history == 0 (0)
* PASS — test: missing_flag_vs_value_mismatch == 0 (0)
* PASS — test: source_flag_wrong == 0 (0)
* PASS — test: june17_masked_non_null == 0 (0)
* PASS — test: june18_diff1_non_null_masked == 0 (0)
* PASS — test: june17_window_mean7_non_null_masked == 0 (0)
* PASS — quality-excluded drives absent from both files ([])
* PASS — each serial has exactly one fold across files (0)
* PASS — drive-held-out: no drive in both train (fold!=k) and test (fold==k) for any k (fold is a deterministic function of serial_number)
* PASS — June 17 rows present in test with core attributes intact (rows=110524, smart_9 non-null=110504)
* PASS — train: positive_rows matches methodology (built=1,842 methodology=1,842)
* PASS — train: positive_drives matches methodology (built=305 methodology=305)
* PASS — train: negative_rows_primary matches methodology (built=5,743,219 methodology=5,743,219)
* PASS — train: negative_rows_sensitivity matches methodology (built=5,740,680 methodology=5,740,680)
* PASS — train: unknown_rows_sensitivity_within_primary_rows matches methodology (built=2,539 methodology=2,539)
* PASS — test: positive_rows matches methodology (built=997 methodology=997)
* PASS — test: positive_drives matches methodology (built=175 methodology=175)
* PASS — test: negative_rows_primary matches methodology (built=2,543,757 methodology=2,543,757)
* PASS — test: negative_rows_sensitivity matches methodology (built=2,542,168 methodology=2,542,168)
* PASS — test: unknown_rows_sensitivity_within_primary_rows matches methodology (built=1,589 methodology=1,589)
* PASS — independent past-only recomputation matches written features (19,422 rows of 300 drives; NaN-pattern mismatches=0; max rel err=4.92e-15)
