#!/usr/bin/env bash
# Trace-driven pilot: shard crc32(serial) % 56 == 0, policies E1 / E2(T0) / E3(T0), T0 in {1,4,12,24,72} h.
# Usage: bash run_pilot.sh <output_dir> [extra ExperimentRunner args...]
# Inputs are read-only Phase-2 outputs. Java 8 runtime, called by absolute path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJ="$(cd "$ROOT/../.." && pwd)"                                  # .../CC_project/project
JAVA8="/c/Program Files/Java/jre1.8.0_501/bin/java.exe"
CP="$(cygpath -m "$ROOT/../vendor/cloudsim-3.0.3/jars/cloudsim-3.0.3.jar");$(cygpath -m "$ROOT/build/classes")"
OUT="$1"; shift
PRED="${PRED:-$(cygpath -m "$PROJ/ml/results/model_evaluation/test_predictions.csv.gz")}"
FAIL="$(cygpath -m "$PROJ/ml/results/dataset_audit_revalidation/drive_failure_summary.csv")"
mkdir -p "$OUT"
"$JAVA8" -Xmx1500m -cp "$CP" ckpt.ExperimentRunner \
    --predictions "$PRED" --failures "$FAIL" --out "$(cygpath -m "$OUT")" \
    --shard 0 --shards 56 --t0 1,4,12,24,72 --hosts-per-dc 50 "$@"
