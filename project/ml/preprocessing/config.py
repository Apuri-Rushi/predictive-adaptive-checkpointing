"""
Central configuration for the 7-day disk-failure dataset pipeline.

Every approved methodology decision lives here (see
project/ml/results/dataset_audit/final_methodology_spec.md), so the other
modules contain no hard-coded constants.
"""
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------------- paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]          # .../CC_project
DATA_DIR = PROJECT_ROOT / "project" / "dataset" / "backblaze_q2_2019"
PROCESSED_DIR = PROJECT_ROOT / "project" / "ml" / "processed"
METHODOLOGY_COUNTS = (PROJECT_ROOT / "project" / "ml" / "results" / "dataset_audit_revalidation"
                      / "target_label_counts.csv")

# ----------------------------------------------------------------------------- target
HORIZON_DAYS = 7

# ----------------------------------------------------------------------------- splits
TRAIN_START, TRAIN_END = pd.Timestamp("2019-04-01"), pd.Timestamp("2019-05-24")
PURGE_START, PURGE_END = pd.Timestamp("2019-05-25"), pd.Timestamp("2019-05-31")
TEST_START, TEST_END = pd.Timestamp("2019-06-01"), pd.Timestamp("2019-06-23")
TAIL_START, TAIL_END = pd.Timestamp("2019-06-24"), pd.Timestamp("2019-06-30")
N_FOLDS = 5                                    # crc32(serial_number) % 5

# ----------------------------------------------------------------------------- data quality
QUALITY_EXCLUDED_SERIALS = {
    "57QEWPXKT": "records after failure record",
    "ZA14EK1F": "failure recorded after 2-day observation gap",
    "VKGMHB0X": "failure recorded after 2-day observation gap",
    "ZCH0D3BM": "failure recorded after 2-day observation gap",
    "ZCH0CJC3": "failure row dated 6/15/19 inside 2019-06-17.csv (date conflict)",
}
ALTERED_FILE_DATE = pd.Timestamp("2019-06-17")
ALTERED_FILE_DAMAGED_COLUMNS = ["smart_7_raw", "smart_188_raw", "smart_231_raw", "smart_232_raw",
                                "smart_240_raw", "smart_241_raw", "smart_242_raw"]

# ----------------------------------------------------------------------------- features
CORE_ATTRIBUTES = [1, 3, 4, 5, 7, 9, 10, 12, 192, 193, 194, 197, 198, 199]   # <= 0.6 % missing
PARTIAL_ATTRIBUTES = [187, 188, 190, 240, 241, 242]                          # 23-25 % missing (model-specific)
ATTRIBUTES = CORE_ATTRIBUTES + PARTIAL_ATTRIBUTES
RAW_COLUMNS = [f"smart_{a}_raw" for a in ATTRIBUTES]
ROLL_WINDOW = 7                                # rolling stats over days t-6 .. t (7 observations)

# Columns that are carried in the output files for grouping/evaluation but are
# NEVER model inputs. The feature manifest lists the complement explicitly.
METADATA_COLUMNS = ["serial_number", "date", "model", "fold", "source_file_altered"]
LABEL_COLUMNS = ["label_primary", "label_sensitivity"]

# CSV writing
FLOAT_FORMAT = "%.15g"                         # keeps exact integers up to ~1e15 (LBA counters ~1e11)
GZIP_LEVEL = 3
