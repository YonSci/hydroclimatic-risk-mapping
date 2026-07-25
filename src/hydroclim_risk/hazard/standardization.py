"""Turn raw indicator values into 0-1 drought/wetness scores.

Every formula here comes from methodology.md's "Standardization formulas"
section. All operate elementwise on xarray DataArrays of any shape/dims (lat,
lon, realization, ...) — they never reduce a dimension, so ensemble-member
structure survives through hazard scoring and is only collapsed later at the
probability-calculation step (quality-safeguards.md).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from hydroclim_risk.config import load_thresholds_config


def _percentile_score(percentile: xr.DataArray, direction: str, cfg: dict[str, Any] | None) -> xr.DataArray:
    """clip((P-50)/40, 0, 1) for direction="high", clip((50-P)/40, 0, 1) for "low"."""
    cfg = cfg or load_thresholds_config()
    scoring = cfg["percentile_scoring"]
    neutral = scoring["neutral_percentile"]
    half_width = scoring["saturation_half_width"]

    if direction == "high":
        raw = (percentile - neutral) / half_width
    elif direction == "low":
        raw = (neutral - percentile) / half_width
    else:
        raise ValueError(f"direction must be 'high' or 'low', got {direction!r}")

    return raw.clip(min=0, max=1)


def _spi_score(spi: xr.DataArray, direction: str, cfg: dict[str, Any] | None) -> xr.DataArray:
    """clip(-SPI/half_width, 0, 1) for direction="dry", clip(SPI/half_width, 0, 1) for "wet".

    half_width is derived from thresholds.yaml's spi.extreme_dry/extreme_wet
    (both must have equal magnitude — SPI=-2.0 -> dry score 1.00,
    SPI=+2.0 -> wet score 1.00, per methodology.md's reference points).
    """
    cfg = cfg or load_thresholds_config()
    spi_cfg = cfg["spi"]
    dry_half_width = abs(float(spi_cfg["extreme_dry"]))
    wet_half_width = abs(float(spi_cfg["extreme_wet"]))
    if not np.isclose(dry_half_width, wet_half_width):
        raise ValueError(
            f"thresholds.yaml spi.extreme_dry ({spi_cfg['extreme_dry']}) and "
            f"spi.extreme_wet ({spi_cfg['extreme_wet']}) must have equal magnitude"
        )

    if direction == "dry":
        raw = -spi / dry_half_width
    elif direction == "wet":
        raw = spi / wet_half_width
    else:
        raise ValueError(f"direction must be 'dry' or 'wet', got {direction!r}")

    return raw.clip(min=0, max=1)


def rainfall_percentile_dry_score(percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """Low rainfall percentile -> drought hazard. 10th percentile or below -> 1.0."""
    return _percentile_score(percentile, "low", cfg)


def rainfall_percentile_wet_score(percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """High rainfall percentile -> wetness hazard. 90th percentile or above -> 1.0."""
    return _percentile_score(percentile, "high", cfg)


def spi_dry_score(spi: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """Negative SPI -> drought hazard. SPI=-2.0 -> 1.0, SPI=-1.0 -> 0.50."""
    return _spi_score(spi, "dry", cfg)


def spi_wet_score(spi: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """Positive SPI -> wetness hazard. SPI=+2.0 -> 1.0, SPI=+1.0 -> 0.50."""
    return _spi_score(spi, "wet", cfg)


def cdd_dry_score(cdd_percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """High CDD percentile -> drought hazard."""
    return _percentile_score(cdd_percentile, "high", cfg)


def cwd_dry_score(cwd_percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """Low CWD percentile -> drought hazard (supporting evidence)."""
    return _percentile_score(cwd_percentile, "low", cfg)


def cwd_wet_score(cwd_percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """High CWD percentile -> wetness hazard."""
    return _percentile_score(cwd_percentile, "high", cfg)


def rx1day_wet_score(rx1day_percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """High Rx1day percentile -> wetness hazard. Wetness-only, never used for drought."""
    return _percentile_score(rx1day_percentile, "high", cfg)


def rx5day_wet_score(rx5day_percentile: xr.DataArray, cfg: dict[str, Any] | None = None) -> xr.DataArray:
    """High Rx5day percentile -> wetness hazard. Wetness-only, never used for drought."""
    return _percentile_score(rx5day_percentile, "high", cfg)
