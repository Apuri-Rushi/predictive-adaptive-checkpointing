"""
Configuration for Phase 2: baseline Random Forest for 7-day disk-failure prediction.
The dataset, labels and features are taken as-is from project/ml/processed/ (Phase 1).
"""
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ML_DIR = PROJECT_ROOT / "project" / "ml"
PROCESSED_DIR = ML_DIR / "processed"
MODELS_DIR = ML_DIR / "models"
RESULTS_DIR = ML_DIR / "results" / "model_evaluation"
FAILURE_SUMMARY = ML_DIR / "results" / "dataset_audit_revalidation" / "drive_failure_summary.csv"

TRAIN_FILE = PROCESSED_DIR / "train_chronological.csv.gz"
TEST_FILE = PROCESSED_DIR / "test_chronological.csv.gz"

# Approved 128 features, in the order recorded by the dataset build.
FEATURES = json.load(open(PROCESSED_DIR / "build_summary.json"))["features"]
assert len(FEATURES) == 128
FORBIDDEN = {"serial_number", "date", "failure", "source_file_altered", "capacity_bytes", "model", "fold",
             "label_primary", "label_sensitivity"}
assert not FORBIDDEN & set(FEATURES)
LABEL = "label_primary"
HORIZON_DAYS = 7

# ---------------------------------------------------------------- sampling (training data only)
SEED = 20190401
NEG_PER_POS = 20
STRATA = ["date", "model"]                  # negatives allocated proportionally across date x model

# ---------------------------------------------------------------- internal time-based validation
FIT_START, FIT_END = pd.Timestamp("2019-04-01"), pd.Timestamp("2019-05-03")
VAL_PURGE_START, VAL_PURGE_END = pd.Timestamp("2019-05-04"), pd.Timestamp("2019-05-10")
VAL_START, VAL_END = pd.Timestamp("2019-05-11"), pd.Timestamp("2019-05-24")
# fit label windows end <= 2019-05-10 < VAL_START
assert FIT_END + pd.Timedelta(days=HORIZON_DAYS) < VAL_START

# ---------------------------------------------------------------- model
BASE_PARAMS = dict(n_estimators=300, max_features="sqrt", bootstrap=True, n_jobs=-1,
                   random_state=SEED, class_weight=None)
GRID = [dict(max_depth=d, min_samples_leaf=m) for d in (10, 20, None) for m in (1, 5, 20)]
SELECTION_METRIC = "pr_auc"                 # on the internal validation set (natural prevalence)
THRESHOLD_RULE = "max_f1_on_validation"     # applied to prior-corrected probabilities

# ---------------------------------------------------------------- evaluation
FPR_POINTS = [0.001, 0.01]
CALIBRATION_BINS = 10                        # quantile bins
PERM_IMPORTANCE_NEG = 50_000                 # validation subsample for permutation importance
PERM_REPEATS = 3
CHUNK = 200_000
