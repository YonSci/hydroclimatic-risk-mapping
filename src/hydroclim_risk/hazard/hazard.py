"""Combine standardized indicator scores into H_dry, H_wet, and the dominant-
hazard layer, per methodology.md.

Never averages H_dry and H_wet (methodology.md: "use max, not average" —
opposite hazard signals would cancel and mask a real hazard). Preserves
whatever dims the input scores carry (lat, lon, realization, ...) — this
module does no reduction, so ensemble-member structure survives for the
probability-calculation step.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from hydroclim_risk.config import load_thresholds_config, load_weights_config
from hydroclim_risk.scoring import weighted_sum


class HazardError(ValueError):
    """Raised when hazard-score inputs don't match the configured weight groups."""


def compute_h_dry(scores: dict[str, xr.DataArray], weights_cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """H_dry = 0.35*spi_dry_score + 0.20*rainfall_percentile_dry_score
    + 0.30*cdd_dry_score + 0.15*cwd_dry_score (weights from config/weights.yaml h_dry).

    `scores` keys must exactly match weights.yaml's h_dry keys — pass the
    outputs of standardization.spi_dry_score / rainfall_percentile_dry_score /
    cdd_dry_score / cwd_dry_score.
    """
    weights_cfg = weights_cfg or load_weights_config()
    return weighted_sum(scores, weights_cfg["h_dry"], "h_dry", HazardError)


def compute_h_wet(scores: dict[str, xr.DataArray], weights_cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """H_wet = 0.20*spi_wet_score + 0.20*rainfall_percentile_wet_score
    + 0.20*cwd_wet_score + 0.15*rx1day_wet_score + 0.25*rx5day_wet_score
    (weights from config/weights.yaml h_wet).
    """
    weights_cfg = weights_cfg or load_weights_config()
    return weighted_sum(scores, weights_cfg["h_wet"], "h_wet", HazardError)


def combine_hazard(h_dry: xr.DataArray, h_wet: xr.DataArray) -> xr.DataArray:
    """H_overall = max(H_dry, H_wet) — never averaged."""
    return np.maximum(h_dry, h_wet)


def dominant_hazard_code(
    h_dry: xr.DataArray,
    h_wet: xr.DataArray,
    threshold: float | None = None,
    thresholds_cfg: dict[str, Any] | None = None,
) -> xr.DataArray:
    """The T / R_dominant categorical layer: 0=none, 1=drought, 2=wet, 3=mixed.

    0 if neither H_dry nor H_wet is >= threshold, 3 if both are, otherwise
    whichever of H_dry/H_wet is substantial determines 1 (drought) or 2 (wet).
    """
    thresholds_cfg = thresholds_cfg or load_thresholds_config()
    if threshold is None:
        threshold = thresholds_cfg["hazard"]["high_hazard_threshold"]
    codes = thresholds_cfg["dominant_hazard_codes"]

    dry_substantial = h_dry >= threshold
    wet_substantial = h_wet >= threshold

    result = xr.where(
        dry_substantial & wet_substantial,
        codes["mixed"],
        xr.where(
            dry_substantial,
            codes["drought"],
            xr.where(wet_substantial, codes["wet"], codes["none"]),
        ),
    )
    # `NaN >= threshold` is False, not NaN, so the xr.where chain above would
    # otherwise silently label no-data cells (e.g. outside the Ethiopia
    # boundary mask) as "no hazard" (code 0) instead of leaving them missing.
    return result.where(np.isfinite(h_dry) & np.isfinite(h_wet))
