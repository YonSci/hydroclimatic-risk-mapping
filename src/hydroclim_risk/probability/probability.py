"""Hazard-exceedance probability and conditional severity from member-level
hazard scores, per methodology.md's "Hazard probability" section.

This is the one place in the pipeline allowed to collapse the `realization`
dimension (quality-safeguards.md: preserve ensemble/year dim through hazard
and severity calculations, only collapse it here). Every function takes
member-level H_dry/H_wet (dims include `realization`) and returns a
grid-only DataArray (realization collapsed).
"""

from __future__ import annotations

import warnings
from typing import Any

import xarray as xr

from hydroclim_risk.config import load_thresholds_config

_REALIZATION_DIM = "realization"


def _get_threshold(threshold: float | None, thresholds_cfg: dict[str, Any] | None) -> float:
    thresholds_cfg = thresholds_cfg or load_thresholds_config()
    return threshold if threshold is not None else thresholds_cfg["hazard"]["high_hazard_threshold"]


def _warn_if_partial_ensemble(n_valid: xr.DataArray, full_size: int) -> None:
    """quality-safeguards.md: warn on insufficient sample size for probability
    calculations. Our current data is all-or-nothing per cell (25 valid or 0),
    but this guards against future ragged/partial ensembles going unnoticed.
    """
    partial = (n_valid > 0) & (n_valid < full_size)
    n_partial = int(partial.sum().values)
    if n_partial > 0:
        warnings.warn(
            f"{n_partial} grid cell(s) have a partial ensemble (fewer than {full_size} valid "
            f"members) — probability/severity there is based on a smaller sample than the full "
            f"ensemble and may be less statistically reliable.",
            stacklevel=3,
        )


def _probability(exceeds: xr.DataArray, valid: xr.DataArray) -> xr.DataArray:
    n_valid = valid.sum(dim=_REALIZATION_DIM)
    n_exceed = exceeds.sum(dim=_REALIZATION_DIM)
    _warn_if_partial_ensemble(n_valid, full_size=valid.sizes[_REALIZATION_DIM])
    return n_exceed / n_valid.where(n_valid > 0)


def compute_p_drought(
    h_dry: xr.DataArray, threshold: float | None = None, thresholds_cfg: dict[str, Any] | None = None
) -> xr.DataArray:
    """P_drought = count(H_dry >= threshold) / total_valid_realizations."""
    threshold = _get_threshold(threshold, thresholds_cfg)
    valid = h_dry.notnull()
    exceeds = (h_dry >= threshold) & valid
    return _probability(exceeds, valid)


def compute_p_wet(
    h_wet: xr.DataArray, threshold: float | None = None, thresholds_cfg: dict[str, Any] | None = None
) -> xr.DataArray:
    """P_wet = count(H_wet >= threshold) / total_valid_realizations."""
    threshold = _get_threshold(threshold, thresholds_cfg)
    valid = h_wet.notnull()
    exceeds = (h_wet >= threshold) & valid
    return _probability(exceeds, valid)


def compute_p_any(
    h_dry: xr.DataArray,
    h_wet: xr.DataArray,
    threshold: float | None = None,
    thresholds_cfg: dict[str, Any] | None = None,
) -> xr.DataArray:
    """P_any = count(H_dry >= threshold OR H_wet >= threshold) / total_valid_realizations."""
    threshold = _get_threshold(threshold, thresholds_cfg)
    valid = h_dry.notnull() & h_wet.notnull()
    exceeds = ((h_dry >= threshold) | (h_wet >= threshold)) & valid
    return _probability(exceeds, valid)


def _conditional_mean(hazard: xr.DataArray, event_mask: xr.DataArray) -> xr.DataArray:
    n = event_mask.sum(dim=_REALIZATION_DIM)
    total = hazard.where(event_mask).sum(dim=_REALIZATION_DIM, skipna=True)
    return total / n.where(n > 0)


def compute_s_drought(
    h_dry: xr.DataArray, threshold: float | None = None, thresholds_cfg: dict[str, Any] | None = None
) -> xr.DataArray:
    """S_drought = mean(H_dry among members classified as drought events).

    NaN at a grid cell if no member there qualifies as a drought event
    (rather than 0 — "no qualifying member" is not the same as "zero severity").
    """
    threshold = _get_threshold(threshold, thresholds_cfg)
    event_mask = (h_dry >= threshold) & h_dry.notnull()
    return _conditional_mean(h_dry, event_mask)


def compute_s_wet(
    h_wet: xr.DataArray, threshold: float | None = None, thresholds_cfg: dict[str, Any] | None = None
) -> xr.DataArray:
    """S_wet = mean(H_wet among members classified as wetness events)."""
    threshold = _get_threshold(threshold, thresholds_cfg)
    event_mask = (h_wet >= threshold) & h_wet.notnull()
    return _conditional_mean(h_wet, event_mask)
