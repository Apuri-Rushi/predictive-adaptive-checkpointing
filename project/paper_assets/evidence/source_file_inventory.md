# Source file inventory

All inputs read (never written) by the paper-asset scripts, with SHA-256 at generation time. In addition, the consistency audit reads all `cloudsim/results/full_rho{0.9,1.0}/shard_*/<policy>/jobs.csv` files (2 × 56 × 11 = 1,232 files); their hashes are recorded in each shard's `OUTPUT_SHA256.txt` and each run's `manifest.csv`.

| File | Role | Size (bytes) | SHA-256 |
|---|---|---|---|
| `ml/results/dataset_audit_revalidation/dataset_summary.txt` | Dataset characteristics (Table 1, Fig. 2) | 5,792 | `acd03c1cfb02e95f…` |
| `ml/results/dataset_audit_revalidation/quality_excluded_drives.csv` | 5 excluded drives (Table 2) | 301 | `f085dfe1543b3ff5…` |
| `ml/processed/dataset_split_summary.csv` | Split counts (Table 2) | 1,145 | `d0243b6ddb7ee515…` |
| `ml/processed/feature_manifest.md` | Feature definitions (Fig. 2) | 5,830 | `fa03a24fbea80184…` |
| `ml/preprocessing/config.py` | Split dates, horizon (Table 2) | 2,922 | `3a8c0eeb64df0169…` |
| `ml/models/random_forest_7d_metadata.json` | Model configuration (Table 3) | 5,762 | `020dd334c6308272…` |
| `ml/results/model_evaluation/validation_metrics.json` | Validation metrics (Table 4) | 1,865 | `84d34a595004510c…` |
| `ml/results/model_evaluation/test_metrics.json` | Test metrics (Table 4, G01–G03) | 2,586 | `dd4c7ba471e6c733…` |
| `ml/results/model_evaluation/test_predictions.csv.gz` | Per-drive-day June scores (G01–G04; CloudSim input) | 35,670,486 | `02d3fce2ab80a690…` |
| `ml/results/model_evaluation/feature_importance.csv` | Feature importance (G05) | 11,664 | `aef20d031b1be664…` |
| `ml/results/model_evaluation/calibration_validation.csv` | Validation P90/P99 (tier-boundary check) | 1,286 | `3355c47220ecbc70…` |
| `cloudsim/research/src/ckpt/policy/Policies.java` | Adaptive multipliers (Table 5, Fig. 3) | 2,069 | `83f2e27bd6b09a5a…` |
| `cloudsim/research/src/ckpt/policy/RiskTierClassifier.java` | Tier boundaries (Table 5, Fig. 3) | 1,285 | `f38b3e8f69ffe9e5…` |
| `cloudsim/research/src/ckpt/sim/SimParams.java` | C, R, D, B, MIPS, deadline (Table 6) | 1,602 | `eb31c5b2a1d74ed7…` |
| `cloudsim/research/src/ckpt/sim/CheckpointingBroker.java` | Execution model (Figs. 4–5) | 19,211 | `b8123c189e2a6dd2…` |
| `cloudsim/research/src/ckpt/sim/FailureInjector.java` | Failure injection (Fig. 4) | 1,401 | `6895bff369e1ffea…` |
| `cloudsim/research/src/ckpt/trace/WorkloadGenerator.java` | Workload model (Table 7) | 2,035 | `9edbd1464aa9fca0…` |
| `cloudsim/research/src/ckpt/trace/RiskTraceLoader.java` | Label exclusion (audit H) | 4,866 | `519be1009dcbd3e4…` |
| `cloudsim/results/full_rho0.9/run_config.json` | Run configuration (Table 6) | 592 | `40d22c7c32dbe192…` |
| `cloudsim/results/full_rho0.9/manifest.csv` | Per-shard status/timing/hashes (Table 15) | 17,564 | `009d6ca03b05e333…` |
| `cloudsim/results/full_rho1.0/manifest.csv` | Per-shard status/timing/hashes (Table 15) | 17,575 | `734c35ff689bf8b1…` |
| `cloudsim/results/full_rho0.9/validation/validation_summary.json` | Validation summary (Table 15) | 395 | `8dbe4286f46b28de…` |
| `cloudsim/results/full_rho1.0/validation/validation_summary.json` | Validation summary (Table 15) | 395 | `97b503cb35255337…` |
| `cloudsim/results/full_rho0.9/validation/validation_by_shard.csv` | Per-shard checks (Table 15, audit H) | 9,239 | `0ca538fd676b9eaa…` |
| `cloudsim/results/full_rho1.0/validation/validation_by_shard.csv` | Per-shard checks (audit H) | 9,209 | `787a37a2963e9ea2…` |
| `cloudsim/results/pilot/PILOT_REPORT.md` | Label-scramble check (audit H) | 10,696 | `70bec28cec8df560…` |
| `cloudsim/results/FINAL_EXPERIMENT_REPORT.md` | Narrative results (audit I) | 23,749 | `79f1b4d433b5baf0…` |
| `cloudsim/results/full_rho0.9/analysis/policy_summary.csv` | Analysis output, ρ = 0.9 | 21,020 | `fb131966783f8e7e…` |
| `cloudsim/results/full_rho0.9/analysis/paired_comparisons.csv` | Analysis output, ρ = 0.9 | 83,532 | `ee4eb70eed69144b…` |
| `cloudsim/results/full_rho0.9/analysis/tier_breakdown.csv` | Analysis output, ρ = 0.9 | 14,342 | `0b040a9db02067dc…` |
| `cloudsim/results/full_rho0.9/analysis/tier_occupancy.csv` | Analysis output, ρ = 0.9 | 220 | `d28e39a16d0ecdb2…` |
| `cloudsim/results/full_rho0.9/analysis/checkpoints_by_tier.csv` | Analysis output, ρ = 0.9 | 3,010 | `57096cc919469223…` |
| `cloudsim/results/full_rho0.9/analysis/failures_detail.csv` | Analysis output, ρ = 0.9 | 148,957 | `8b91d7cdda8a54a0…` |
| `cloudsim/results/full_rho0.9/analysis/analysis_meta.json` | Analysis output, ρ = 0.9 | 443 | `d4aac2cbe80296bc…` |
| `cloudsim/results/full_rho1.0/analysis/policy_summary.csv` | Analysis output, ρ = 1.0 | 22,185 | `4e21a55776ecb903…` |
| `cloudsim/results/full_rho1.0/analysis/paired_comparisons.csv` | Analysis output, ρ = 1.0 | 85,198 | `cd456b7417d0eb78…` |
| `cloudsim/results/full_rho1.0/analysis/tier_breakdown.csv` | Analysis output, ρ = 1.0 | 14,926 | `d86450de0e106aaf…` |
| `cloudsim/results/full_rho1.0/analysis/tier_occupancy.csv` | Analysis output, ρ = 1.0 | 220 | `d28e39a16d0ecdb2…` |
| `cloudsim/results/full_rho1.0/analysis/checkpoints_by_tier.csv` | Analysis output, ρ = 1.0 | 3,026 | `4cd3b1812dd913bc…` |
| `cloudsim/results/full_rho1.0/analysis/failures_detail.csv` | Analysis output, ρ = 1.0 | 153,544 | `5dd30b2d18a8081e…` |
| `cloudsim/results/full_rho1.0/analysis/analysis_meta.json` | Analysis output, ρ = 1.0 | 443 | `7c05d691161075c0…` |

## Generated assets

| Path | Count |
|---|---|
| `paper_assets/architecture/` | 18 files |
| `paper_assets/graphs/random_forest/` | 15 files |
| `paper_assets/graphs/checkpointing_primary/` | 21 files |
| `paper_assets/graphs/saturated_sensitivity/` | 15 files |
| `paper_assets/graphs/risk_analysis/` | 12 files |
| `paper_assets/tables/csv/` | 17 files |
| `paper_assets/tables/latex/` | 17 files |

Scripts (`paper_assets/scripts/`): `common.py`, `make_diagrams.py`, `make_rf_graphs.py`, `make_result_graphs.py`, `make_tables.py`, `consistency_check.py`, `make_docs.py`. Re-generate everything with:

```
cd project/paper_assets/scripts
python make_diagrams.py && python make_rf_graphs.py && python make_result_graphs.py
python make_tables.py && python consistency_check.py && python make_docs.py
```
