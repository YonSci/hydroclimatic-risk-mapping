"""Generic GeoTIFF QC scanner -- formalizes the ad-hoc per-file min/max/
mean/n_valid checks used throughout this project's development (see project
memory: data_qc_findings, project_exposure_module, project_vulnerability_
module) into reusable, tested code, per quality-safeguards.md's "check these
explicitly in code... not just by eye."
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from hydroclim_risk.config import PROJECT_ROOT


def generate_qc_report(directory: Path | str, pattern: str = "*.tif") -> pd.DataFrame:
    """Scan every file in `directory` matching `pattern` (non-recursive, so
    a quarantine subfolder like _deprecated_mislabeled/ is naturally
    excluded) and return a tidy DataFrame with descriptive stats per file:
    n_valid, n_total, pct_valid, n_inf, min, max, mean, std, is_constant.
    """
    directory = Path(directory)
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory

    rows = []
    for path in sorted(directory.glob(pattern)):
        with rasterio.open(path) as src:
            arr = src.read(1).astype("float64")
        n_total = arr.size
        n_inf = int(np.isinf(arr).sum())
        valid = arr[np.isfinite(arr)]
        n_valid = valid.size
        rows.append(
            {
                "file": path.name,
                "n_valid": n_valid,
                "n_total": n_total,
                "pct_valid": n_valid / n_total if n_total else np.nan,
                "n_inf": n_inf,
                "min": float(valid.min()) if n_valid else np.nan,
                "max": float(valid.max()) if n_valid else np.nan,
                "mean": float(valid.mean()) if n_valid else np.nan,
                "std": float(valid.std()) if n_valid else np.nan,
                "is_constant": bool(n_valid and valid.std() == 0),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["file", "n_valid", "n_total", "pct_valid", "n_inf", "min", "max", "mean", "std", "is_constant"],
    )


def validate_bounds(report: pd.DataFrame, min_value: float, max_value: float, tolerance: float = 1e-6) -> pd.DataFrame:
    """Return the subset of `report` rows (from generate_qc_report) whose
    min/max fall outside [min_value, max_value] -- an empty result means
    every scanned file passed. Does not raise -- callers decide what to do
    with violations, mirroring how QC was done manually throughout this
    project's development: report first, decide second.
    """
    if report.empty:
        return report
    return report[(report["min"] < min_value - tolerance) | (report["max"] > max_value + tolerance)]


def validate_no_infs_or_constants(report: pd.DataFrame) -> pd.DataFrame:
    """Return the subset of `report` rows with any Inf values or a constant
    (zero-variance) valid region -- both are red flags found repeatedly
    during this project's real-data QC passes (see project memory).
    """
    if report.empty:
        return report
    return report[(report["n_inf"] > 0) | (report["is_constant"])]
