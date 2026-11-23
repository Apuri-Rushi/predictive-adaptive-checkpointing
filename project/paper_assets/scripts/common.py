"""Shared style, colours, paths and loaders for the paper-asset scripts.

Read-only with respect to the project: every function here only READS ML / CloudSim outputs.
All generated files go under project/paper_assets/.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]          # .../project
ASSETS = PROJECT / "paper_assets"
ML = PROJECT / "ml"
MLEVAL = ML / "results" / "model_evaluation"
CS = PROJECT / "cloudsim"
RES = CS / "results"
ANALYSIS = {"0.9": RES / "full_rho0.9" / "analysis", "1.0": RES / "full_rho1.0" / "analysis"}
VALIDATION = {"0.9": RES / "full_rho0.9" / "validation", "1.0": RES / "full_rho1.0" / "validation"}

# IEEE two-column geometry (inches)
COL_W = 3.5
DBL_W = 7.16

# ---- colours (validated with the dataviz validator, light mode, surface white) ----
C_E1 = "#8c8b87"      # neutral grey: baseline (no checkpointing)
C_E2 = "#2a78d6"      # categorical slot 1, blue: fixed interval
C_E3 = "#eb6834"      # categorical slot 2, orange: RF-adaptive
POLICY_COLOR = {"E1": C_E1, "E2": C_E2, "E3": C_E3}
POLICY_LABEL = {"E1": "E1 No checkpointing", "E2": "E2 Fixed interval", "E3": "E3 RF-adaptive"}
# Risk tiers: always shown with direct labels + hatching (CVD secondary encoding)
TIER_COLOR = {"LOW": "#1baf7a", "MEDIUM": "#eda100", "HIGH": "#e34948"}
TIER_HATCH = {"LOW": "", "MEDIUM": "///", "HIGH": "xxx"}
TIERS = ["LOW", "MEDIUM", "HIGH"]
INK = "#1a1a1a"
INK2 = "#52514e"
GRID = "#dcdcd8"

T0S = [1, 4, 12, 24, 72]


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "text.color": INK,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "axes.axisbelow": True,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "hatch.linewidth": 0.5,
        "pdf.fonttype": 42,        # embed TrueType (IEEE PDF eXpress friendly)
        "ps.fonttype": 42,
        "svg.fonttype": "path",    # SVG renders identically without the font installed
        "lines.linewidth": 1.5,
    })


def save(fig, outdir: Path, stem: str, formats=("png", "pdf", "svg")) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in formats:
        p = outdir / f"{stem}.{ext}"
        kw = {"dpi": 300} if ext == "png" else {}
        fig.savefig(p, bbox_inches="tight", pad_inches=0.02, metadata=None if ext != "png" else None, **kw)
        paths.append(p)
    plt.close(fig)
    return paths


# ---------------------------------------------------------------- loaders
def policy_summary(rho: str) -> pd.DataFrame:
    return pd.read_csv(ANALYSIS[rho] / "policy_summary.csv")


def paired(rho: str) -> pd.DataFrame:
    return pd.read_csv(ANALYSIS[rho] / "paired_comparisons.csv")


def pol(kind: str, t0: int | None = None) -> str:
    """Policy id as used in the analysis CSVs."""
    if kind == "E1":
        return "E1_none"
    return f"{'E2_fixed' if kind == 'E2' else 'E3_adaptive'}_T0_{t0}h"


def getv(df: pd.DataFrame, stratum: str, policy: str, metric: str, suffix: str = "") -> float:
    row = df[(df.stratum == stratum) & (df.policy == policy)]
    assert len(row) == 1, (stratum, policy)
    return float(row[metric + suffix].iloc[0])


def getpair(df: pd.DataFrame, stratum: str, a: str, b: str, metric: str) -> pd.Series:
    row = df[(df.stratum == stratum) & (df.comparison == f"{a} - {b}") & (df.metric == metric)]
    assert len(row) == 1, (stratum, a, b, metric)
    return row.iloc[0]


def load_json(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))
