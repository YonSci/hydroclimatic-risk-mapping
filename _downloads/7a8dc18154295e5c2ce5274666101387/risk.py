"""Combine probability, severity, exposure, and vulnerability into
R_drought, R_wet, the dominant-risk layer, and risk classes, per
methodology.md's Risk calculation:

  R_drought = 100 * P_drought * S_drought * E * V_drought
  R_wet     = 100 * P_wet * S_wet * E * V_wet

R is a relative 0-100 score, NOT a probability percentage. Computed PER
EXPOSURE SECTOR (population, cropland, livestock, ...) since exposure/
deliberately keeps sectors separate (methodology.md: don't blend
incompatible physical units into one index) -- there is no single combined
"E", so the caller supplies one sector's normalized exposure array per call;
see risk/pipeline.py for the orchestration that loops over periods/sectors.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hydroclim_risk.config import load_thresholds_config


def compute_risk(p: np.ndarray, s: np.ndarray, e: np.ndarray, v: np.ndarray) -> np.ndarray:
    """R = 100 * P * S * E * V (methodology.md's Risk calculation).

    S (conditional severity) is NaN wherever P=0 by design (probability.py:
    "no qualifying member" is not "zero severity", so it's left undefined
    rather than silently 0). But 0 * NaN = NaN in IEEE arithmetic, which
    would wrongly make R undefined at every zero-probability cell instead of
    correctly 0. Where P is exactly 0 (not NaN -- a real "no hazard
    observed" result, as opposed to missing/masked hazard data), S is
    treated as 0 for this computation: zero probability means zero risk
    regardless of an undefined conditional severity. R still stays NaN if E
    or V themselves are NaN (genuinely missing exposure/vulnerability data),
    and still stays NaN if P itself is NaN (missing/masked hazard data).
    """
    s_effective = np.where((p == 0) & np.isfinite(p), 0.0, s)
    return 100.0 * p * s_effective * e * v


def combine_dominant_risk(r_drought: np.ndarray, r_wet: np.ndarray) -> np.ndarray:
    """R_dominant = max(R_drought, R_wet) -- never averaged, same reasoning
    as hazard's H_overall (opposite signals shouldn't cancel).
    """
    return np.maximum(r_drought, r_wet)


def dominant_risk_code(
    r_drought: np.ndarray,
    r_wet: np.ndarray,
    threshold: float | None = None,
    thresholds_cfg: dict[str, Any] | None = None,
) -> np.ndarray:
    """0=insignificant, 1=drought-dominated, 2=wet-dominated, 3=mixed/compound.

    `threshold` defaults to the top of the "Very low" risk class (see
    thresholds.yaml's risk_classes) -- i.e. a risk within the "Very low"
    band is treated as insignificant/no identified risk. Reuses
    thresholds.yaml's dominant_hazard_codes (same 0/1/2/3 scheme as
    hazard.dominant_hazard_code, per methodology.md's note to keep the two
    layers' codes consistent).
    """
    thresholds_cfg = thresholds_cfg or load_thresholds_config()
    if threshold is None:
        very_low = next(c for c in thresholds_cfg["risk_classes"] if c["label"] == "Very low")
        threshold = very_low["max"]
    codes = thresholds_cfg["dominant_hazard_codes"]

    drought_significant = r_drought > threshold
    wet_significant = r_wet > threshold

    result = np.where(
        drought_significant & wet_significant,
        codes["mixed"],
        np.where(
            drought_significant,
            codes["drought"],
            np.where(wet_significant, codes["wet"], codes["none"]),
        ),
    )
    valid = np.isfinite(r_drought) & np.isfinite(r_wet)
    return np.where(valid, result, np.nan)


def classify_risk(r: np.ndarray, thresholds_cfg: dict[str, Any] | None = None) -> np.ndarray:
    """Map a continuous 0-100 risk score to its risk-class code (0-4), per
    thresholds.yaml's risk_classes (Very low/Low/Moderate/High/Very high).
    NaN input (or a value outside all configured bands) maps to NaN.
    """
    thresholds_cfg = thresholds_cfg or load_thresholds_config()
    result = np.full(r.shape, np.nan, dtype="float64")
    for cls in thresholds_cfg["risk_classes"]:
        in_range = (r >= cls["min"]) & (r <= cls["max"]) & np.isfinite(r)
        result = np.where(in_range, float(cls["code"]), result)
    return result
