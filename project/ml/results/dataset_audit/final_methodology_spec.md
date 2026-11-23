# Final Methodology Specification — 7-Day Disk-Failure Target (Backblaze Q2 2019)

**Project:** Predictive Disk Failure-Aware Adaptive Checkpointing for Fault-Tolerant Cloud Task Scheduling
**Status:** integrity verification and specification only. No training set was created, no model was trained, and CloudSim was not modified.

**Legend:**
* **[VERIFIED]** — measured on the data by the scripts listed in §9.
* **[SPEC]** — the approved or proposed methodology; not yet executed.

---

## 1. Stage 1 — Restoring `2019-06-17.csv`: NOT POSSIBLE from local sources  [VERIFIED]

| Check | Result |
|---|---|
| Original Q2 2019 archive found locally | `C:\Users\rushi\CC_project\data_Q2_2019.zip` (574,522,473 bytes; ZIP CRC test passed; 91 CSV members plus `__MACOSX` metadata) |
| Archive's `2019-06-17.csv` vs local file | **Byte-identical.** Both have SHA-256 `2cb4dcbbc0f51a679e5e0bda5171fb4bd386769030e88290be0a9d99630927e0` and 33,116,249 bytes |
| Archive member timestamp | 2019-07-29 12:10:24. The dominant member date is 2019-07-03, so this member was written separately |
| All 91 local files vs archive | **91/91 identical** (CRC32 and size) |

* The spreadsheet-altered version is **already inside the downloaded archive**, so no unaltered June 17 file exists locally.
* Following the instructions, **Stage 1 stopped here**:
  * the file was **not** backed up, replaced or edited;
  * no values were reconstructed;
  * nothing was downloaded.
* **A decision is needed (§8):** whether to request an unaltered copy from Backblaze, or to keep the file with the handling rules in §6.

## 2. Stage 2 — Revalidation of all 91 files  [VERIFIED]

The new results are in `project/ml/results/dataset_audit_revalidation/`; the original audit in `dataset_audit/` was kept unchanged.

| Check | Result |
|---|---|
| Headers | Identical in all 91 files (129 columns: 5 identifiers plus 62 SMART IDs × normalized/raw) |
| Dates | 2019-04-01 … 2019-06-30, 91 of 91 days present. **90 files** use ISO `YYYY-MM-DD`. **`2019-06-17.csv`** uses `M/D/YY` in all 110,533 rows; 1 row (ZCH0CJC3, `failure = 1`) is dated `6/15/19` |
| Row counts | 9,831,138 drive-days; 105,624–110,718 per day. June 17 has 110,533 rows, and no drive present on both 06-16 and 06-18 is missing from it |
| Duplicate drive-day records | 0 |
| Duplicate full rows | 0 |
| Failure labels | Only {0, 1}: 500 records with `failure = 1`, from 500 drives (one each) |
| Other invalid values | No missing serial or model; no negative or non-numeric SMART values; no normalized value outside 0–255; 663 rows with `capacity_bytes` ≤ 0 (not used as a feature) |
| Spreadsheet conversion issues | **Only in `2019-06-17.csv`.** It uses bare carriage-return line endings, `M/D/YY` dates and re-ordered rows, and **58,779 values were rounded into scientific notation**: `smart_242_raw` 58,500, `smart_7_raw` 90, `smart_231_raw` 56, `smart_232_raw` 56, `smart_241_raw` 48, `smart_188_raw` 27, `smart_240_raw` 2. No other file shows any conversion marker |
| Audit outcome | The rerun reproduces the original audit exactly |

### Updated dataset statistics  [VERIFIED]

| Item | Value |
|---|---|
| Drives | 111,817 across 42 models |
| Failed drives | 500 |
| Never-failed drives | 111,317: 110,640 present on 30 June; 677 left before then (censored) |
| Observations before failure | median 44 (0–89); 488 failed drives have ≥ 1 prior observation |
| Raw SMART attributes with ≤ 0.6 % missing | 1, 3, 4, 5, 7, 9, 10, 12, 192, 193, 194, 197, 198, 199 |
| Raw SMART attributes 23–25 % missing | 187, 188, 190, 240, 241, 242 |
| Raw SMART attributes > 50 % missing | 34 |
| Raw SMART attributes 100 % missing | 7 |
| Failures from the top three models | ST12000NM0007, ST4000DM000 and ST8000NM0055: 407 of 500 (81 %) |

## 3. Target definition  [SPEC; counts VERIFIED]

* **Observation day:** the date in the file name. The row's `date` field is checked against it but not used.
* **Failure day F:** the file date of the drive's `failure = 1` record.
* **Horizon:** H = 7 days.

| Class | Rule for a record of drive *d* on day *t* |
|---|---|
| **Excluded (failure or after)** | t ≥ F: the failure-day record and any later record |
| **Positive (1)** | t < F ≤ t + 7: a failure record on day t+1 … t+7 |
| **Primary negative (0)** | No failure record in t+1 … t+7, **and** *d* has an observation on or after t+7 |
| **Sensitivity negative (0)** | No failure record in t+1 … t+7, **and** *d* has observations on **all** days t+1 … t+7 |
| **Unknown → excluded** | Neither positive nor negative under the chosen rule: the drive's follow-up ends before t+7 (end of data, or removed without a failure record) or, for the sensitivity rule, a day is missing from the window |

The primary-negative rule is sound because in this dataset a failed drive never reappears, with one exception that is excluded below. A record on or after t+7 with no failure record therefore shows the drive was still operational through day t+7.

**Drives excluded for data quality** (all records, both as inputs and as labels):

| Serial | Reason |
|---|---|
| 57QEWPXKT | Has records after its failure record |
| ZA14EK1F | Failure recorded after a 2-day observation gap |
| VKGMHB0X | Failure recorded after a 2-day observation gap |
| ZCH0D3BM | Failure recorded after a 2-day observation gap |
| ZCH0CJC3 | Failure row dated `6/15/19` inside the June 17 file; the failure date is ambiguous |

The list is in `quality_excluded_drives.csv`.

### Label counts  [VERIFIED — `target_label_counts.csv`]

| Scope | Positive rows (drives) | Primary negatives | Unknown (primary) | Sensitivity negatives | Unknown (sensitivity) | Neg : Pos (primary) |
|---|---|---|---|---|---|---|
| All observations | 3,195 (483) | 9,050,211 | 777,054 | 9,045,785 | 781,480 | 2,833 : 1 |
| **Train, 04-01 … 05-24** | **1,842 (305)** | **5,743,219** | 2,091 | 5,740,680 | 4,630 | 3,118 : 1 |
| Purge, 05-25 … 05-31 (not examples) | 283 (76) | 763,235 | 18 | 762,937 | 316 | — |
| **Test, 06-01 … 06-23** | **997 (175)** | **2,543,757** | 209 | 2,542,168 | 1,798 | 2,551 : 1 |
| Tail, 06-24 … 06-30 (not examples) | 73 (30) | 0 | 774,736 | 0 | 774,736 | — |

Also excluded: 495 failure-day records and 183 records from the quality-excluded drives.

* The two negative definitions differ by only about 0.05 % of negatives.
* **Effective sample size is drives, not rows:** 305 positive drives for training and 175 for testing.

## 4. Input features and history  [SPEC; history coverage VERIFIED]

* Features for record (d, t) may use **only records of drive d dated ≤ t**. That means current SMART values and past-only derived features such as lags, deltas and rolling statistics.
* **History must be tracked, not assumed.**
  * Store, with each example, the number of observations in [t−7, t−1] and a flag `history_complete_7d`.
  * Compute derived features from time-indexed windows. Leave a value as NaN when the needed past record is missing; never zero-fill or forward-fill across gaps.
  * **[VERIFIED]** 86.7 % of eligible training rows have a complete 7-day history; the shortfall is mostly the first week of April, because the dataset starts on 2019-04-01. The figure is 99.5 % for test rows.
  * 1,636 of 1,842 training positives and 988 of 997 test positives have a complete history.
* **Candidate attributes:**
  * the 14 raw attributes with ≤ 0.6 % missing (§2);
  * 187, 188, 190, 240, 241 and 242 only with an explicit "not reported" indicator, since they are missing for whole drive models.

  Feature selection is a later, reviewed step.
* **Never used as features:**
  * `serial_number`, `date`, day-of-year, the `failure` column, or `capacity_bytes` as a stand-in for drive identity;
  * any record dated after t;
  * drive lifetime aggregates such as last-seen date or total observation count;
  * any statistic computed using the purge or test periods.

## 5. Validation  [SPEC; split counts VERIFIED]

### 5.1 Primary: chronological

| Part | Example rows (observation dates) | Rule |
|---|---|---|
| Training | 2019-04-01 … 2019-05-24 | Every label window ends by 05-31, so none reaches the test period (checked by an assertion in the script) |
| Purge | 2019-05-25 … 2019-05-31 | **Not used as examples.** The raw records stay available as *outcomes* for training labels and as *history* for test features |
| Testing | 2019-06-01 … 2019-06-23 | Label windows end by 06-30 |
| Tail | 2019-06-24 … 2019-06-30 | Not examples (unknown outcome). Records may still serve as outcomes for test labels |

Further rules:
* Any class balancing (downsampling or class weights), imputation, scaling or threshold choice is fitted on **training rows only**.
* Hyperparameter tuning uses a time-blocked split inside the training period with its own 7-day purge, for example fitting on 04-01 … 05-03 and validating on 05-11 … 05-24.

### 5.2 Secondary: drive-held-out with time separation (proposed)

* Each drive goes to one of 5 groups by `crc32(serial_number) % 5`. The serial number is used **only for grouping**.
* For fold *k*:
  * **training:** training-period rows of drives *not* in group *k*;
  * **testing:** test-period rows of drives in group *k*.
* Each test drive is unseen in training, and the train/test time separation of §5.1 is kept.
* Predictions from the 5 folds are pooled, so every test drive is scored once by a model that never saw it.

**[VERIFIED — `drive_heldout_fold_counts.csv`]**

| Fold | Training positives: rows / drives | Test positives: rows / drives | Test drives | Drives in both train and test |
|---|---|---|---|---|
| 0 | 1,460 / 243 | 219 / 39 | 22,218 | **0** |
| 1 | 1,444 / 240 | 163 / 27 | 22,000 | **0** |
| 2 | 1,474 / 246 | 225 / 41 | 22,049 | **0** |
| 3 | 1,474 / 244 | 207 / 37 | 22,220 | **0** |
| 4 | 1,516 / 247 | 183 / 31 | 22,361 | **0** |

Pooled over the folds, the test set has 997 positive rows from 175 drives, the same as §5.1. Folds are not stratified; with 27–41 positive drives per fold, report pooled metrics plus the spread between folds.

### 5.3 Metrics (proposed)

* **Per row:** PR-AUC; recall at fixed false-positive rates (0.1 %, 1 %); Brier score and calibration curve, since probabilities feed the checkpoint scheduler.
* **Per drive:** share of failing drives flagged at least once in their last 7 days, and the lead time; false alarms per 1,000 drive-days.
* **By model**, given that 81 % of failures come from three models.

## 6. Leakage-prevention safeguards  [SPEC]

1. Failure-day and post-failure records are never inputs or examples.
2. Unknown outcomes are excluded and never counted as negative.
3. Features come only from records dated ≤ t of the same drive, using time-based windows with NaN for missing history.
4. No training label window crosses into the test period (enforced by the purge and an assertion).
5. All preprocessing, balancing and tuning is fitted on training rows only.
6. `serial_number` is used only for grouping; drive-held-out folds have 0 drive overlap.
7. Quality-excluded drives are removed entirely.
8. **`2019-06-17.csv` handling, if the file is not replaced:**
   * Use the file date (2019-06-17) for every row.
   * Do not trust the rounded columns on that day: set `smart_7_raw`, `smart_188_raw`, `smart_231_raw`, `smart_232_raw`, `smart_240_raw`, `smart_241_raw` and `smart_242_raw` to NaN for 06-17 only. Do **not** reconstruct them. Add a `source_file_altered` flag.
   * Also treat any derived feature whose window includes 06-17 as incomplete for those columns.
   * Impact: 110,533 test-period rows (45 of them positive), plus derived features for 06-18 … 06-24.

## 7. Remaining limitations  [VERIFIED facts / interpretation]

* `2019-06-17.csv` is altered at its source, the archive itself (§1).
* Short window: 91 days.
* 98 % of failed drives were present on day 1, so history before 2019-04-01 is unknown (left truncation).
* Strong class imbalance: about 2,800 negatives per positive.
* Positives are concentrated in three Seagate models.
* Positive rows from the same drive are highly correlated: about 6.6 rows per positive drive.
* Some SMART attributes are missing for whole models, so missingness encodes the model.
* Results describe **drive** failure. Mapping them to CloudSim host or VM failure is a modelling assumption to state explicitly.

## 8. Decision required before any training data is created

1. **June 17 file:** either
   * (a) authorise a download of a fresh Q2 2019 archive from Backblaze and re-verify it; it may be identical if the official release carries the same file. Or
   * (b) accept the file with the safeguards in §6.8.
2. Approve the quality exclusion of the 5 drives listed in §3.

## 9. Reproducibility

Run from `C:\Users\rushi\CC_project`:

```
python -I project/ml/preprocessing/verify_provenance.py
python -I project/ml/preprocessing/inspect_dataset.py --out project/ml/results/dataset_audit_revalidation
python -I project/ml/preprocessing/target_feasibility_counts.py
```

Outputs are in `project/ml/results/dataset_audit_revalidation/`:
* `provenance_check.csv`, `spreadsheet_conversion_cells.csv`
* `dataset_summary.txt`, `file_integrity.csv`, `daily_failure_counts.csv`, `drive_failure_summary.csv`, `smart_missing_values.csv`, `model_failure_summary.csv`
* `target_label_counts.csv`, `drive_heldout_fold_counts.csv`, `quality_excluded_drives.csv`
* run logs

The first audit in `project/ml/results/dataset_audit/` is unchanged, apart from this new file.
