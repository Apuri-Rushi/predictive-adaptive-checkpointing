"""Captions, source mapping, file inventory, Overleaf folder + example project, and the ZIP.

Run after make_diagrams.py, make_rf_graphs.py, make_result_graphs.py, make_tables.py, consistency_check.py.
"""
import hashlib
import json
import re
import shutil
import zipfile

import common as C

A = C.ASSETS
OVL = A / "overleaf"
SCRIPTS = "paper_assets/scripts"

# --------------------------------------------------------------------------------------------- figures
# (stem, folder, label, width, placement, caption, demonstrates, sources, script)
AN9, AN1 = "cloudsim/results/full_rho0.9/analysis", "cloudsim/results/full_rho1.0/analysis"
MLE = "ml/results/model_evaluation"
FIGS = [
    ("fig01_system_architecture", "architecture", "fig:system_architecture", "dbl", "Sec. III (Proposed system), first figure",
     "Overall architecture of the proposed system. The offline pipeline (top) trains a Random Forest on Backblaze SMART "
     "data (1 April -- 24 May 2019) and writes one prior-corrected 7-day failure score per drive-day for 1--23 June. Only "
     "these scores enter the trace-driven CloudSim simulation (bottom), where a risk classifier and an adaptive checkpoint "
     "scheduler set each host's checkpoint interval. Failure times come from a separate trace that only the failure "
     "injector reads; failure labels are never passed to the simulator. Orange borders: custom components; grey: native CloudSim.",
     "Separation of offline ML training from online simulation, and the single interface (daily scores) between them.",
     ["ml/models/random_forest_7d_metadata.json", "cloudsim/research/src/ckpt/**", "cloudsim/results/full_rho0.9/run_config.json"],
     "make_diagrams.py:fig1"),
    ("fig02_ml_pipeline", "architecture", "fig:ml_pipeline", "col", "Sec. III-A (Failure prediction)",
     "Random Forest prediction pipeline. Steps 1--8 run offline; step 9 (risk classification) is applied inside the "
     "simulator. Labels use a 7-day horizon: a drive-day is positive if the drive records a failure on day t+1 to t+7. "
     "The tier boundaries are the 90th and 99th percentiles of validation scores and were not tuned on test data.",
     "Exact preprocessing, labelling, split, sampling, training, prior correction and tiering steps with their parameters.",
     ["ml/results/dataset_audit_revalidation/dataset_summary.txt", "ml/processed/dataset_split_summary.csv",
      "ml/models/random_forest_7d_metadata.json", "cloudsim/research/src/ckpt/policy/RiskTierClassifier.java"],
     "make_diagrams.py:fig2"),
    ("fig03_adaptive_checkpointing", "architecture", "fig:adaptive", "col", "Sec. III-B (Adaptive checkpoint scheduling)",
     "Adaptive checkpoint scheduling (policy E3). The Random Forest supplies only a risk score. A fixed classifier maps the "
     "score to a tier, and the scheduler maps the tier to a checkpoint interval $\\tau$ relative to the baseline $T_0$. "
     "The table lists the resulting intervals for each $T_0$; the fixed policy E2 uses $\\tau = T_0$ for every tier.",
     "That the RF predicts risk, not intervals; the exact tier-to-interval rules (2.65$T_0$, $T_0$, $T_0$/4.9).",
     ["cloudsim/research/src/ckpt/policy/Policies.java", "cloudsim/research/src/ckpt/policy/RiskTierClassifier.java",
      "cloudsim/research/src/ckpt/risk/DailyScoreTimeline.java"], "make_diagrams.py:fig3"),
    ("fig04_cloudsim_integration", "architecture", "fig:cloudsim", "dbl", "Sec. III-C (CloudSim integration)",
     "CloudSim integration and recovery architecture. Native CloudSim 3.0.3 entities (grey) are used unmodified. The "
     "custom broker runs each job as a chain of compute-segment cloudlets and writes each checkpoint as a 300 s cloudlet. "
     "On a host failure it moves the job to a spare host and restores from the last completed checkpoint. Each Backblaze "
     "drive is modelled as one host, and a recorded disk failure is treated as a host failure; this is a modelling assumption.",
     "Which parts are custom versus native CloudSim; how checkpoint state, failure injection, spare hosts and recovery are realised.",
     ["cloudsim/research/src/ckpt/sim/*.java", "cloudsim/research/src/ckpt/trace/*.java", "cloudsim/SETUP_LOG.md"],
     "make_diagrams.py:fig4"),
    ("fig05_execution_flow", "architecture", "fig:execution_flow", "dbl", "Sec. III-C, after Fig. cloudsim",
     "End-to-end execution flow for one job. A job runs in compute segments that end at the next checkpoint due time, at "
     "midnight (when the daily risk tier may change) or at job end. A host failure interrupts the running segment or "
     "checkpoint write. The job then resumes on a spare host after $D + B = 180$ s: from its last completed checkpoint "
     "after a 300 s restore, or from zero if no checkpoint exists.",
     "The runtime decision logic: tier lookup, interval selection, checkpoint commit, failure handling, restore vs restart.",
     ["cloudsim/research/src/ckpt/sim/CheckpointingBroker.java", "cloudsim/research/src/ckpt/sim/SimParams.java"],
     "make_diagrams.py:fig5"),
    ("fig06_experimental_design", "architecture", "fig:experimental_design", "dbl", "Sec. IV (Experimental setup)",
     "Experimental design. In each scenario, all 11 policy configurations (E1, plus E2 and E3 at five baseline intervals "
     "$T_0$) run on all 56 shards with the identical workload, failure trace and risk trace, so comparisons are paired. "
     "The two load scenarios ($\\rho = 0.9$ primary, $\\rho = 1.0$ saturated sensitivity) have different workloads and are "
     "analysed separately.",
     "Common inputs, the 11 policy runs, collected metrics and the paired statistical comparison; scenario separation.",
     ["cloudsim/research/scripts/run_full.py", "cloudsim/research/validation/analyze_full.py",
      f"{AN9}/analysis_meta.json", f"{AN1}/analysis_meta.json"], "make_diagrams.py:fig6"),
    # ---- RF
    ("g01_rf_roc_curve", "graphs/random_forest", "fig:rf_roc", "col", "Sec. V-A (Prediction results)",
     "ROC curve of the Random Forest on the 1--23 June test set (2,544,754 drive-days, 997 positives). (a) Full curve, "
     "AUC = 0.804. (b) The same curve with a logarithmic FPR axis; markers show recall at 0.1\\,\\% FPR (16.0\\,\\%) and "
     "1\\,\\% FPR (37.3\\,\\%).",
     "Discrimination over the whole range and in the low-FPR region that matters operationally.",
     [f"{MLE}/test_predictions.csv.gz", f"{MLE}/test_metrics.json"], "make_rf_graphs.py"),
    ("g02_rf_precision_recall_curve", "graphs/random_forest", "fig:rf_pr", "col", "Sec. V-A",
     "Precision--recall curve on the June test set (PR-AUC = 0.0337, about 86 times the 0.039\\,\\% prevalence; "
     "log-scaled precision axis). The marker shows the alarm threshold 0.01368 chosen by maximum F1 on validation: "
     "precision 4.3\\,\\%, recall 20.7\\,\\%.",
     "Performance under extreme class imbalance; the operating point used for alarms.",
     [f"{MLE}/test_predictions.csv.gz", f"{MLE}/test_metrics.json"], "make_rf_graphs.py"),
    ("g03_rf_confusion_matrix", "graphs/random_forest", "fig:rf_cm", "col", "Sec. V-A",
     "Confusion matrix on the June test set at the validation-selected threshold ($p \\ge 0.01368$). Shading shows the "
     "row-normalised rate. The model raises 4,597 false alarms for 206 true positives and misses 79\\,\\% of positive drive-days.",
     "The concrete error counts behind the precision/recall figures.",
     [f"{MLE}/test_predictions.csv.gz", f"{MLE}/test_metrics.json"], "make_rf_graphs.py"),
    ("g04_rf_score_distribution", "graphs/random_forest", "fig:rf_scores", "col", "Sec. V-A or V-D (tiers)",
     "Distribution of prior-corrected scores (log scale) for June drive-days with and without a failure in the next 7 "
     "days, each normalised to 100\\,\\%. Dotted lines mark the tier boundaries (0.000234, 0.001732) and the alarm threshold "
     "(0.01368). The two classes overlap substantially.",
     "Score separation between classes and where the fixed tier boundaries cut the June distribution.",
     [f"{MLE}/test_predictions.csv.gz", "cloudsim/research/src/ckpt/policy/RiskTierClassifier.java"], "make_rf_graphs.py"),
    ("g05_rf_feature_importance", "graphs/random_forest", "fig:rf_importance", "dbl", "Sec. V-A",
     "Top 15 features. (a) Mean decrease in impurity, final model. (b) Permutation importance (mean decrease in average "
     "precision $\\pm$ s.d.) of the internal-validation model on a validation subsample. Reallocated-sector counts "
     "(SMART 5) dominate both rankings. Correlated features share importance, so the rankings should be read in groups.",
     "Which SMART attributes and temporal transformations drive the predictions.",
     [f"{MLE}/feature_importance.csv"], "make_rf_graphs.py"),
    # ---- primary
    ("g06_overhead_vs_T0_rho09", "graphs/checkpointing_primary", "fig:overhead_rho09", "col", "Sec. V-B (Primary results)",
     "Checkpoint overhead as a percentage of useful computation for fixed (E2) and RF-adaptive (E3) checkpointing at each "
     "baseline interval $T_0$, $\\rho = 0.9$, all hosts (log scale; E1 has no overhead). Whiskers are 95\\,\\% host-clustered "
     "bootstrap CIs and are very narrow. E3 is lower at $T_0 \\le 12$\\,h and higher at 24--72\\,h.",
     "Overhead cost of each policy across baselines.", [f"{AN9}/policy_summary.csv"], "make_result_graphs.py"),
    ("g07_lost_work_vs_T0_rho09", "graphs/checkpointing_primary", "fig:lost_rho09", "col", "Sec. V-B",
     "Lost computation caused by the 175 host failures, $\\rho = 0.9$ (log scale). The dashed line shows no checkpointing "
     "(E1, 8,375\\,h). Whiskers are 95\\,\\% bootstrap CIs; they are wide because they rest on 175 failure events.",
     "Protection against lost work for each policy and baseline.", [f"{AN9}/policy_summary.csv"], "make_result_graphs.py"),
    ("g08_deadline_miss_vs_T0_rho09", "graphs/checkpointing_primary", "fig:deadline_rho09", "dbl", "Sec. V-B",
     "Deadline miss rate, $\\rho = 0.9$. (a) All hosts: only E3 at $T_0 = 1$\\,h misses an appreciable share (4.54\\,\\%). "
     "Every other E2/E3 configuration misses at most 0.015\\,\\%; value labels below 0.05\\,\\% are omitted. (b) The 175 "
     "failing hosts: E1 misses 19.8\\,\\%, and E3 at 1\\,h misses 23.3\\,\\%. Whiskers are 95\\,\\% bootstrap CIs.",
     "Deadline impact overall and on the hosts that fail (negative result for E3 at 1 h shown).",
     [f"{AN9}/policy_summary.csv"], "make_result_graphs.py"),
    ("g09_wasted_time_all_policies_rho09", "graphs/checkpointing_primary", "fig:wasted_rho09", "col", "Sec. V-B",
     "Total wasted time (checkpoint overhead + lost work + interrupted checkpoint writes + recovery) as a percentage of "
     "useful computation, $\\rho = 0.9$ (log scale). No checkpointing (E1) wastes the least overall (0.011\\,\\%). At these "
     "failure rates, checkpointing pays off by protecting the jobs that failures hit (Fig.~\\ref{fig:deadline_rho09}b), "
     "not in aggregate efficiency.",
     "Aggregate efficiency of all 11 configurations, including the unfavourable comparison with E1.",
     [f"{AN9}/policy_summary.csv"], "make_result_graphs.py"),
    ("g10_overhead_vs_lost_tradeoff_rho09", "graphs/checkpointing_primary", "fig:tradeoff_rho09", "col", "Sec. V-B",
     "Trade-off between overhead and lost computation, $\\rho = 0.9$ (log--log). Each point is one policy at one $T_0$; "
     "labels are on the E2 points, and the E3 point for the same $T_0$ lies just below. E3 is lower on both axes at "
     "$T_0 \\le 12$\\,h; the 1\\,h point carries a deadline penalty (Fig.~\\ref{fig:deadline_rho09}). At 24 and 72\\,h, E3 "
     "trades higher overhead for lower lost work. Whiskers: 95\\,\\% CIs of lost work.",
     "Whether E3 shifts the overhead/lost-work frontier relative to E2.", [f"{AN9}/policy_summary.csv"], "make_result_graphs.py"),
    ("g11_checkpoints_per_job_rho09", "graphs/checkpointing_primary", "fig:ckpts_rho09", "col", "Sec. V-B",
     "Mean checkpoints per job, $\\rho = 0.9$ (log scale). E3 writes fewer checkpoints than E2 at $T_0 \\le 12$\\,h, "
     "because 54\\,\\% of June host-days are LOW, and more at 24--72\\,h.",
     "Checkpoint frequency underlying the overhead differences.", [f"{AN9}/policy_summary.csv"], "make_result_graphs.py"),
    ("g12_paired_E3_vs_E2_rho09", "graphs/checkpointing_primary", "fig:paired_rho09", "dbl", "Sec. V-B (statistical comparison)",
     "Paired E3 $-$ E2 differences at equal $T_0$, $\\rho = 0.9$, all hosts: (a)--(c) relative to E2, (d) in percentage "
     "points. Intervals are 95\\,\\% host-clustered bootstrap CIs of the difference, rescaled by the E2 point estimate in "
     "(a)--(c). Filled markers: the interval excludes 0. Negative values favour E3. The intervals are not adjusted for "
     "multiple comparisons, and no significance is claimed.",
     "Direction, size and uncertainty of every primary E3-vs-E2 effect in one view.",
     [f"{AN9}/paired_comparisons.csv"], "make_result_graphs.py"),
    # ---- saturated
    ("g12_paired_E3_vs_E2_rho10", "graphs/saturated_sensitivity", "fig:paired_rho10", "dbl", "Sec. V-C (Saturated sensitivity)",
     "Paired E3 $-$ E2 differences at equal $T_0$ under saturation, $\\rho = 1.0$, all hosts. The format is the same as "
     "Fig.~\\ref{fig:paired_rho09}. This experiment has a different workload from $\\rho = 0.9$, so its effects are "
     "compared only in direction and size.",
     "Whether the primary effects persist without idle slack.", [f"{AN1}/paired_comparisons.csv"], "make_result_graphs.py"),
    ("g13_deadline_miss_vs_T0_rho10", "graphs/saturated_sensitivity", "fig:deadline_rho10", "col", "Sec. V-C",
     "Deadline miss rate under saturation, $\\rho = 1.0$, all hosts. Without slack, checkpoint overhead becomes queueing "
     "delay: at $T_0 = 1$\\,h, E2 misses 50.7\\,\\% of deadlines and E3 34.2\\,\\%; at 4\\,h, 7.6\\,\\% versus 3.2\\,\\%. At "
     "12\\,h, E3 is worse (0.27\\,\\% versus 0.01\\,\\%).",
     "Deadline sensitivity to saturation, including the unfavourable 12 h result.", [f"{AN1}/policy_summary.csv"],
     "make_result_graphs.py"),
    ("g14_queueing_vs_T0_rho10", "graphs/saturated_sensitivity", "fig:queue_rho10", "col", "Sec. V-C",
     "Mean queueing delay per job, $\\rho = 1.0$ (log scale). E3 reduces queueing at every $T_0$. The dashed line shows "
     "E1 (0.04\\,h).",
     "How overhead turns into queueing delay under saturation.", [f"{AN1}/policy_summary.csv"], "make_result_graphs.py"),
    ("g15_lost_work_vs_T0_rho10", "graphs/saturated_sensitivity", "fig:lost_rho10", "col", "Sec. V-C",
     "Lost computation, $\\rho = 1.0$ (log scale), with 95\\,\\% bootstrap CIs. The dashed line shows E1 (9,603\\,h).",
     "Lost-work protection under saturation.", [f"{AN1}/policy_summary.csv"], "make_result_graphs.py"),
    ("g16_failing_host_deadline_miss_both_rho", "graphs/saturated_sensitivity", "fig:failing_deadline", "dbl", "Sec. V-C",
     "Deadline miss rate on the 175 failing hosts, fixed (E2) versus adaptive (E3): (a) $\\rho = 0.9$, (b) $\\rho = 1.0$. "
     "Under saturation, E3's extra checkpoints on HIGH-tier hosts raise failing-host deadline misses at $T_0 \\le 4$\\,h "
     "(25.5\\,\\% versus 14.9\\,\\% at 4\\,h), even though lost work falls. The two panels are separate experiments with "
     "different workloads.",
     "The main negative finding: the saturation penalty on the hosts E3 is meant to protect.",
     [f"{AN9}/policy_summary.csv", f"{AN1}/policy_summary.csv"], "make_result_graphs.py"),
    # ---- risk
    ("g17_tier_occupancy", "graphs/risk_analysis", "fig:tier_occupancy", "col", "Sec. V-D (Risk tiers and distribution shift)",
     "Share of June host-days in each risk tier, compared with the validation design target (90/9/1\\,\\%). June scores "
     "are shifted upward: only 54.1\\,\\% of host-days are LOW, and 6.6\\,\\% are HIGH. Failing hosts spend 52.3\\,\\% of "
     "their host-days in HIGH.",
     "Distribution shift between validation and June, and that the ranking still separates failing hosts.",
     [f"{AN9}/tier_occupancy.csv", f"{AN1}/tier_occupancy.csv"], "make_result_graphs.py"),
    ("g18_failures_by_tier", "graphs/risk_analysis", "fig:failures_tier", "col", "Sec. V-D",
     "Risk tier in force at the instant of each of the 175 failures, identical across policies and scenarios: 110 HIGH, "
     "38 MEDIUM and 27 LOW.",
     "How often the predictor had the failing host in the right tier at failure time.",
     [f"{AN9}/failures_detail.csv", f"{AN1}/failures_detail.csv"], "make_result_graphs.py"),
    ("g19_lost_work_by_tier_rho09", "graphs/risk_analysis", "fig:lost_tier_rho09", "dbl", "Sec. V-D",
     "Lost computation grouped by the tier in force at failure, $\\rho = 0.9$ (log scale; point estimates). E3 sharply "
     "reduces lost work for failures in HIGH and has little effect in MEDIUM. It increases lost work for the 27 failures "
     "the model ranked LOW, where its interval is 2.65\\,$T_0$.",
     "Where the adaptive policy helps (model right) and hurts (model wrong).",
     [f"{AN9}/failures_detail.csv"], "make_result_graphs.py"),
    ("g20_overhead_by_tier_rho09", "graphs/risk_analysis", "fig:overhead_tier_rho09", "col", "Sec. V-D",
     "Checkpoint overhead split by the tier in force when each checkpoint was written, $\\rho = 0.9$, all hosts, indexed "
     "to the E2 total at the same $T_0$ (= 100). E3 cuts LOW-tier overhead and spends much of the saving on HIGH-tier "
     "checkpoints. At $T_0 = 72$\\,h the LOW interval (190.8\\,h) exceeds the longest job (168\\,h), so E3 writes almost "
     "no LOW-tier checkpoints (0.2\\,\\% of its checkpoints).",
     "Where the overhead budget goes; the cost of the distribution shift on healthy HIGH-tier hosts.",
     [f"{AN9}/checkpoints_by_tier.csv"], "make_result_graphs.py"),
]

# Recommended manuscript selection: main paper vs supplementary
MAIN = ["fig01_system_architecture", "fig02_ml_pipeline", "fig03_adaptive_checkpointing", "fig04_cloudsim_integration",
        "fig05_execution_flow", "fig06_experimental_design", "g01_rf_roc_curve", "g02_rf_precision_recall_curve",
        "g10_overhead_vs_lost_tradeoff_rho09", "g08_deadline_miss_vs_T0_rho09", "g12_paired_E3_vs_E2_rho09",
        "g16_failing_host_deadline_miss_both_rho", "g17_tier_occupancy", "g19_lost_work_by_tier_rho09"]
MAIN_TABLES = ["tab01_dataset", "tab04_rf_performance", "tab05_tiers", "tab06_cloudsim_config", "tab07_workload",
               "tab08_policy_rho09", "tab09_paired_rho09", "tab11_paired_rho10", "tab12_failing_nonfailing_rho09",
               "tab13_tier_occupancy", "tab15_execution_validation"]


def sha(p, n=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(n)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def md_escape_tex(s):
    """Plain-markdown version of a LaTeX caption."""
    for a, b in [("\\,", " "), ("\\%", "%"), ("$-$", "−"), ("\\le", "≤"), ("\\ge", "≥"), ("\\pm", "±"),
                 ("\\tau", "τ"), ("\\rho", "ρ"), ("T_0", "T0"), ("--", "–"), ("~\\ref{", " \\ref{")]:
        s = s.replace(a, b)
    s = re.sub(r"\\ref\{([^}]+)\}", r"[\1]", s)
    s = s.replace("$", "").replace("\\", "")
    return s


def write_captions():
    tabs = json.loads((A / "tables" / "table_index.json").read_text(encoding="utf-8"))
    L = ["# Figure captions", "",
         "LaTeX-ready captions are in `overleaf/captions_figures.tex` (one `\\newcommand` per figure); this file is the readable version.",
         "Width: `col` = single column (`figure`, `\\columnwidth`), `dbl` = full width (`figure*`, `\\textwidth`).", ""]
    for i, (stem, folder, label, w, place, cap, dem, srcs, scr) in enumerate(FIGS, 1):
        L += [f"## {stem}", "", f"* **File:** `{folder}/{stem}.{{pdf,svg,png}}`  (Overleaf: `figures/{stem}.pdf`)",
              f"* **Label:** `{label}`   **Width:** {w}   **Recommended placement:** {place}"
              f"   **Main paper:** {'yes' if stem in MAIN else 'supplementary / optional'}",
              f"* **Caption:** {md_escape_tex(cap)}", f"* **Demonstrates:** {md_escape_tex(dem)}", ""]
    (A / "captions" / "figure_captions.md").write_text("\n".join(L), encoding="utf-8")
    L = ["# Table captions", "", "IEEE style: captions go above tables; every `.tex` file already contains its "
         "`\\caption` and `\\label`.", ""]
    for t in tabs:
        L += [f"## Table {t['number']}: {t['stem']}", "",
              f"* **Files:** `tables/latex/{t['stem']}.tex`, `tables/csv/{t['stem']}.csv`",
              f"* **Label:** `{t['label']}`   **Width:** {'full (table*)' if t['wide'] else 'single column'}"
              f"   **Main paper:** {'yes' if t['stem'] in MAIN_TABLES else 'supplementary / optional'}",
              f"* **Caption:** {t['caption']}", f"* **Table note:** {t['notes'] or '—'}", ""]
    (A / "captions" / "table_captions.md").write_text("\n".join(L), encoding="utf-8")
    return tabs


def write_sources(tabs):
    L = ["# Figure and table data sources", "",
         "Every figure is regenerated by the listed script. Plotted values for G01–G20 are also saved next to the figures in "
         "`graphs/<group>/data/*.csv`. All paths are relative to `project/`.", "", "## Figures", "",
         "| Figure | Script | Source files | Plotted-data file |", "|---|---|---|---|"]
    for stem, folder, label, w, place, cap, dem, srcs, scr in FIGS:
        data = list((A / folder / "data").glob(f"{stem}*.csv")) if (A / folder / "data").exists() else []
        if stem.startswith("g0") and int(stem[1:3]) <= 5:
            data = [p for p in (A / folder / "data").glob(f"g{stem[1:3]}*")]
        L.append(f"| `{stem}` | `{SCRIPTS}/{scr}` | {'<br>'.join(f'`{s}`' for s in srcs)} | "
                 f"{'<br>'.join(f'`paper_assets/{folder}/data/{p.name}`' for p in data) or '— (diagram; labels from source code)'} |")
    L += ["", "## Tables", "", "| Table | Label | Source files |", "|---|---|---|"]
    for t in tabs:
        L.append(f"| {t['number']} `{t['stem']}` | `{t['label']}` | {'<br>'.join(f'`{s}`' for s in t['sources'])} |")
    L += ["", "## Metric definitions used everywhere", "",
          "* **Deadline miss rate (%)** = late jobs / all jobs × 100; deadline = submit + 1.5 × job length.",
          "* **Lost computation (h)** = useful work since the last completed checkpoint (or job start) at the failure instant.",
          "* **Checkpoint overhead (h)** = 300 s × completed checkpoint writes; **% of useful** divides by the sum of job lengths.",
          "* **Wasted time (% of useful)** = (overhead + lost + interrupted checkpoint writes + recovery) / useful × 100.",
          "* **Queueing delay (h/job)** = mean time from submit to start.",
          "* **Recovery (h)** = D + B (+ R if a checkpoint exists) summed over failures that interrupted a job.",
          "* **Paired difference** = E3 − E2 at the same T0 in the same scenario; CI = percentile 95 % from a host-clustered "
          "Poisson(1) bootstrap (B = 2,000, seed 20190601). Shards are not statistical samples. No multiplicity correction; "
          "no p-values; no significance claims.", ""]
    (A / "evidence" / "figure_data_sources.md").write_text("\n".join(L), encoding="utf-8")


def write_inventory():
    P = C.PROJECT
    files = [
        ("ml/results/dataset_audit_revalidation/dataset_summary.txt", "Dataset characteristics (Table 1, Fig. 2)"),
        ("ml/results/dataset_audit_revalidation/quality_excluded_drives.csv", "5 excluded drives (Table 2)"),
        ("ml/processed/dataset_split_summary.csv", "Split counts (Table 2)"),
        ("ml/processed/feature_manifest.md", "Feature definitions (Fig. 2)"),
        ("ml/preprocessing/config.py", "Split dates, horizon (Table 2)"),
        ("ml/models/random_forest_7d_metadata.json", "Model configuration (Table 3)"),
        ("ml/results/model_evaluation/validation_metrics.json", "Validation metrics (Table 4)"),
        ("ml/results/model_evaluation/test_metrics.json", "Test metrics (Table 4, G01–G03)"),
        ("ml/results/model_evaluation/test_predictions.csv.gz", "Per-drive-day June scores (G01–G04; CloudSim input)"),
        ("ml/results/model_evaluation/feature_importance.csv", "Feature importance (G05)"),
        ("ml/results/model_evaluation/calibration_validation.csv", "Validation P90/P99 (tier-boundary check)"),
        ("cloudsim/research/src/ckpt/policy/Policies.java", "Adaptive multipliers (Table 5, Fig. 3)"),
        ("cloudsim/research/src/ckpt/policy/RiskTierClassifier.java", "Tier boundaries (Table 5, Fig. 3)"),
        ("cloudsim/research/src/ckpt/sim/SimParams.java", "C, R, D, B, MIPS, deadline (Table 6)"),
        ("cloudsim/research/src/ckpt/sim/CheckpointingBroker.java", "Execution model (Figs. 4–5)"),
        ("cloudsim/research/src/ckpt/sim/FailureInjector.java", "Failure injection (Fig. 4)"),
        ("cloudsim/research/src/ckpt/trace/WorkloadGenerator.java", "Workload model (Table 7)"),
        ("cloudsim/research/src/ckpt/trace/RiskTraceLoader.java", "Label exclusion (audit H)"),
        ("cloudsim/results/full_rho0.9/run_config.json", "Run configuration (Table 6)"),
        ("cloudsim/results/full_rho0.9/manifest.csv", "Per-shard status/timing/hashes (Table 15)"),
        ("cloudsim/results/full_rho1.0/manifest.csv", "Per-shard status/timing/hashes (Table 15)"),
        ("cloudsim/results/full_rho0.9/validation/validation_summary.json", "Validation summary (Table 15)"),
        ("cloudsim/results/full_rho1.0/validation/validation_summary.json", "Validation summary (Table 15)"),
        ("cloudsim/results/full_rho0.9/validation/validation_by_shard.csv", "Per-shard checks (Table 15, audit H)"),
        ("cloudsim/results/full_rho1.0/validation/validation_by_shard.csv", "Per-shard checks (audit H)"),
        ("cloudsim/results/pilot/PILOT_REPORT.md", "Label-scramble check (audit H)"),
        ("cloudsim/results/FINAL_EXPERIMENT_REPORT.md", "Narrative results (audit I)"),
    ]
    for rho in ("0.9", "1.0"):
        for f in ["policy_summary.csv", "paired_comparisons.csv", "tier_breakdown.csv", "tier_occupancy.csv",
                  "checkpoints_by_tier.csv", "failures_detail.csv", "analysis_meta.json"]:
            files.append((f"cloudsim/results/full_rho{rho}/analysis/{f}", f"Analysis output, ρ = {rho}"))
    L = ["# Source file inventory", "",
         "All inputs read (never written) by the paper-asset scripts, with SHA-256 at generation time. In addition, the "
         "consistency audit reads all `cloudsim/results/full_rho{0.9,1.0}/shard_*/<policy>/jobs.csv` files "
         "(2 × 56 × 11 = 1,232 files); their hashes are recorded in each shard's `OUTPUT_SHA256.txt` and each run's `manifest.csv`.",
         "", "| File | Role | Size (bytes) | SHA-256 |", "|---|---|---|---|"]
    for f, role in files:
        p = P / f
        L.append(f"| `{f}` | {role} | {p.stat().st_size:,} | `{sha(p)[:16]}…` |")
    L += ["", "## Generated assets", "", "| Path | Count |", "|---|---|"]
    for sub in ["architecture", "graphs/random_forest", "graphs/checkpointing_primary", "graphs/saturated_sensitivity",
                "graphs/risk_analysis", "tables/csv", "tables/latex"]:
        n = len([x for x in (A / sub).iterdir() if x.is_file()])
        L.append(f"| `paper_assets/{sub}/` | {n} files |")
    L += ["", "Scripts (`paper_assets/scripts/`): `common.py`, `make_diagrams.py`, `make_rf_graphs.py`, `make_result_graphs.py`, "
          "`make_tables.py`, `consistency_check.py`, `make_docs.py`. Re-generate everything with:", "", "```",
          "cd project/paper_assets/scripts", "python make_diagrams.py && python make_rf_graphs.py && python make_result_graphs.py",
          "python make_tables.py && python consistency_check.py && python make_docs.py", "```", ""]
    (A / "evidence" / "source_file_inventory.md").write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------------------------- Overleaf
def fig_env(stem, label, w, cap):
    env, width = ("figure*", "\\textwidth") if w == "dbl" else ("figure", "\\columnwidth")
    if stem in ("g08_deadline_miss_vs_T0_rho09", "g16_failing_host_deadline_miss_both_rho"):
        width = "0.75\\textwidth"
    if stem in ("g03_rf_confusion_matrix", "g18_failures_by_tier"):
        width = "0.8\\columnwidth"
    return (f"\\begin{{{env}}}[!t]\n  \\centering\n  \\includegraphics[width={width}]{{figures/{stem}.pdf}}\n"
            f"  \\caption{{{cap}}}\n  \\label{{{label}}}\n\\end{{{env}}}\n")


BIB = r"""% Core references for the methods used. VERIFY every entry against the publisher record before submission.
@article{breiman2001random,
  author  = {Breiman, Leo},
  title   = {Random Forests},
  journal = {Machine Learning},
  volume  = {45},
  number  = {1},
  pages   = {5--32},
  year    = {2001}
}
@article{calheiros2011cloudsim,
  author  = {Calheiros, Rodrigo N. and Ranjan, Rajiv and Beloglazov, Anton and De Rose, C{\'e}sar A. F. and Buyya, Rajkumar},
  title   = {{CloudSim}: a toolkit for modeling and simulation of cloud computing environments and evaluation of resource provisioning algorithms},
  journal = {Software: Practice and Experience},
  volume  = {41},
  number  = {1},
  pages   = {23--50},
  year    = {2011}
}
@article{young1974first,
  author  = {Young, John W.},
  title   = {A first order approximation to the optimum checkpoint interval},
  journal = {Communications of the ACM},
  volume  = {17},
  number  = {9},
  pages   = {530--531},
  year    = {1974}
}
@article{daly2006higher,
  author  = {Daly, J. T.},
  title   = {A higher order estimate of the optimum checkpoint interval for restart dumps},
  journal = {Future Generation Computer Systems},
  volume  = {22},
  number  = {3},
  pages   = {303--312},
  year    = {2006}
}
@inproceedings{elkan2001foundations,
  author    = {Elkan, Charles},
  title     = {The Foundations of Cost-Sensitive Learning},
  booktitle = {Proc. 17th International Joint Conference on Artificial Intelligence (IJCAI)},
  pages     = {973--978},
  year      = {2001}
}
@inproceedings{dalpozzolo2015calibrating,
  author    = {Dal Pozzolo, Andrea and Caelen, Olivier and Johnson, Reid A. and Bontempi, Gianluca},
  title     = {Calibrating Probability with Undersampling for Unbalanced Classification},
  booktitle = {Proc. IEEE Symposium Series on Computational Intelligence (SSCI)},
  pages     = {159--166},
  year      = {2015}
}
@article{pedregosa2011scikit,
  author  = {Pedregosa, F. and Varoquaux, G. and Gramfort, A. and Michel, V. and Thirion, B. and Grisel, O. and others},
  title   = {Scikit-learn: Machine Learning in {P}ython},
  journal = {Journal of Machine Learning Research},
  volume  = {12},
  pages   = {2825--2830},
  year    = {2011}
}
@book{efron1993bootstrap,
  author    = {Efron, Bradley and Tibshirani, Robert J.},
  title     = {An Introduction to the Bootstrap},
  publisher = {Chapman \& Hall},
  year      = {1993}
}
@inproceedings{pinheiro2007failure,
  author    = {Pinheiro, Eduardo and Weber, Wolf-Dietrich and Barroso, Luiz Andr{\'e}},
  title     = {Failure Trends in a Large Disk Drive Population},
  booktitle = {Proc. 5th USENIX Conference on File and Storage Technologies (FAST)},
  year      = {2007}
}
@misc{backblaze_data,
  author       = {{Backblaze, Inc.}},
  title        = {Hard Drive Data and Stats},
  howpublished = {\url{https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data}},
  note         = {Q2 2019 data set; accessed ADD-DATE}
}
"""


def build_overleaf(tabs):
    if OVL.exists():
        shutil.rmtree(OVL)
    (OVL / "figures").mkdir(parents=True)
    (OVL / "tables").mkdir()
    (OVL / "references").mkdir()
    for stem, folder, *_ in FIGS:
        shutil.copy2(A / folder / f"{stem}.pdf", OVL / "figures" / f"{stem}.pdf")
    for t in tabs:
        shutil.copy2(A / "tables" / "latex" / f"{t['stem']}.tex", OVL / "tables" / f"{t['stem']}.tex")
    (OVL / "references" / "references.bib").write_text(BIB, encoding="utf-8")
    # captions as macros
    cl = ["% Figure captions as macros: \\input{captions_figures} then use e.g. \\CapFigSystemArchitecture",
          "% Generated by paper_assets/scripts/make_docs.py"]
    for stem, folder, label, w, place, cap, *_ in FIGS:
        cl.append(f"\\newcommand{{\\Cap{macro(stem)}}}{{{cap}}}")
    (OVL / "captions_figures.tex").write_text("\n".join(cl) + "\n", encoding="utf-8")
    # inclusion examples
    ex = ["% ================================================================",
          "% Reusable inclusion examples (copy into the manuscript).",
          "% Preamble needs: \\usepackage{graphicx,booktabs,amsmath,url}",
          "% ================================================================", "",
          "% --- single-column figure ---", fig_env("g10_overhead_vs_lost_tradeoff_rho09", "fig:tradeoff_rho09", "col",
                                                    "\\CapGTenOverheadVsLostTradeoffRhoZeroNine"),
          "% --- full-width figure (two columns) ---", fig_env("fig01_system_architecture", "fig:system_architecture", "dbl",
                                                                "\\CapFigZeroOneSystemArchitecture"),
          "% --- table (each .tex file already contains table/table*, caption and label) ---",
          "\\input{tables/tab09_paired_rho09}", "",
          "% --- cross-references ---",
          "% As shown in Fig.~\\ref{fig:tradeoff_rho09} and Table~\\ref{tab:paired_rho09}, ...", ""]
    (OVL / "latex_inclusion_examples.tex").write_text("\n".join(ex), encoding="utf-8")
    # standalone example project: all assets in recommended order
    body = []
    body.append("\\section{Figures and tables recommended for the main paper}")
    for stem, folder, label, w, place, cap, *_ in FIGS:
        if stem in MAIN:
            body.append(fig_env(stem, label, w, f"\\Cap{macro(stem)}"))
    for t in tabs:
        if t["stem"] in MAIN_TABLES:
            body.append(f"\\input{{tables/{t['stem']}}}")
    body.append("\\clearpage\n\\section{Supplementary figures and tables}")
    for stem, folder, label, w, place, cap, *_ in FIGS:
        if stem not in MAIN:
            body.append(fig_env(stem, label, w, f"\\Cap{macro(stem)}"))
    for t in tabs:
        if t["stem"] not in MAIN_TABLES:
            body.append(f"\\input{{tables/{t['stem']}}}")
    refs = ", ".join(f"Fig.~\\ref{{{lab}}}" for s, _, lab, *_ in FIGS if s in MAIN)
    main = (
        "% Asset preview project (NOT the paper). Compiles on Overleaf with pdfLaTeX + BibTeX.\n"
        "\\documentclass[conference]{IEEEtran}\n\\usepackage[T1]{fontenc}\n\\usepackage{graphicx}\n\\usepackage{booktabs}\n"
        "\\usepackage{amsmath}\n\\usepackage{url}\n\\usepackage{cite}\n\\input{captions_figures}\n\n"
        "\\begin{document}\n"
        "\\title{Asset Preview: Predictive Disk Failure-Aware Adaptive Checkpointing}\n"
        "\\author{\\IEEEauthorblockN{Evidence package --- not the manuscript}}\n\\maketitle\n\n"
        "\\begin{abstract}\nThis document only typesets the generated figures and tables so that their size, legibility and "
        "numbering can be checked in IEEE two-column format. It contains no paper text.\n\\end{abstract}\n\n"
        f"Cross-reference test: {refs}; Tables~\\ref{{tab:dataset}}--\\ref{{tab:execution}}. "
        "Method citations: \\cite{breiman2001random,calheiros2011cloudsim,young1974first,daly2006higher,"
        "elkan2001foundations,dalpozzolo2015calibrating,pedregosa2011scikit,efron1993bootstrap,pinheiro2007failure,backblaze_data}.\n\n"
        + "\n".join(body) +
        "\n\\bibliographystyle{IEEEtran}\n\\bibliography{references/references}\n\\end{document}\n")
    (OVL / "main.tex").write_text(main, encoding="utf-8")
    (OVL / "README.md").write_text(
        "# Overleaf assets\n\n* `main.tex`: standalone preview project (IEEEtran, pdfLaTeX). Upload the ZIP to Overleaf "
        "(New Project → Upload Project) and compile; it typesets every figure and table.\n"
        "* `figures/*.pdf`: vector figures (PNG 300 dpi and SVG versions are in `paper_assets/`).\n"
        "* `tables/*.tex`: booktabs tables with caption and label; include with `\\input{tables/<name>}`.\n"
        "* `captions_figures.tex`: figure captions as macros (`\\Cap...`).\n"
        "* `latex_inclusion_examples.tex`: copy-paste patterns.\n"
        "* `references/references.bib`: method references; verify each entry before submission.\n\n"
        "Required packages: graphicx, booktabs, amsmath, url, cite (all available on Overleaf).\n", encoding="utf-8")


def macro(stem):
    words = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven",
             "8": "Eight", "9": "Nine"}
    s = stem.replace("rho0.9", "RhoZeroNine").replace("rho1.0", "RhoOneZero")
    s = s.replace("g10", "GTen").replace("g11", "GEleven").replace("g12", "GTwelve").replace("g13", "GThirteen")
    s = s.replace("g14", "GFourteen").replace("g15", "GFifteen").replace("g16", "GSixteen").replace("g17", "GSeventeen")
    s = s.replace("g18", "GEighteen").replace("g19", "GNineteen").replace("g20", "GTwenty")
    out = "".join(p[:1].upper() + p[1:] for p in re.split(r"[_.]", s) if p)
    return "".join(words.get(ch, ch) for ch in out)


def lint_tex():
    probs = []
    for p in list((OVL / "tables").glob("*.tex")) + [OVL / "main.tex", OVL / "latex_inclusion_examples.tex",
                                                      OVL / "captions_figures.tex"]:
        s = p.read_text(encoding="utf-8")
        body = re.sub(r"(?<!\\)%.*", "", s)
        if body.count("{") - body.count("\\{") != body.count("}") - body.count("\\}"):
            probs.append((p.name, "brace imbalance"))
        for env in set(re.findall(r"\\begin\{(\w+\*?)\}", body)):
            if body.count(f"\\begin{{{env}}}") != body.count(f"\\end{{{env}}}"):
                probs.append((p.name, f"unbalanced {env}"))
        if body.count("$") % 2:
            probs.append((p.name, "odd number of $"))
        if any(ord(ch) > 127 for ch in body):
            probs.append((p.name, "non-ASCII: " + "".join(sorted({ch for ch in body if ord(ch) > 127}))))
    for m in re.findall(r"\\includegraphics\[[^]]*\]\{([^}]+)\}", (OVL / "main.tex").read_text(encoding="utf-8")):
        if not (OVL / m).exists():
            probs.append(("main.tex", f"missing {m}"))
    for m in re.findall(r"\\input\{([^}]+)\}", (OVL / "main.tex").read_text(encoding="utf-8")):
        if not ((OVL / m).exists() or (OVL / (m + ".tex")).exists()):
            probs.append(("main.tex", f"missing input {m}"))
    labels = re.findall(r"\\label\{([^}]+)\}", "".join(p.read_text(encoding="utf-8") for p in (OVL / "tables").glob("*.tex"))
                        + (OVL / "main.tex").read_text(encoding="utf-8"))
    dup = {x for x in labels if labels.count(x) > 1}
    if dup:
        probs.append(("labels", f"duplicate {dup}"))
    return probs, len(labels)


def build_zip():
    z = A / "overleaf_assets.zip"
    if z.exists():
        z.unlink()
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(OVL.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(OVL).as_posix())
    return z


def main():
    (A / "captions").mkdir(exist_ok=True)
    tabs = write_captions()
    write_sources(tabs)
    write_inventory()
    build_overleaf(tabs)
    probs, nlab = lint_tex()
    z = build_zip()
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    (A / "evidence" / "latex_lint.json").write_text(json.dumps({"problems": probs, "labels": nlab,
                                                                "zip_entries": len(names)}, indent=1), encoding="utf-8")
    print("lint problems:", probs, "| labels:", nlab, "| zip entries:", len(names), "| zip bytes:", z.stat().st_size)


if __name__ == "__main__":
    main()
