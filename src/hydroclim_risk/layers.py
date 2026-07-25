"""Shared helpers for reading already-acquired exposure/vulnerability
GeoTIFFs and normalizing them -- used by both exposure/ and vulnerability/,
which both start from the same outputs/exposure_vulnerability/ layers (see
acquisition/) and both normalize via methodology.md's robust 5th/95th-
percentile convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

from hydroclim_risk.config import PROJECT_ROOT, load_data_config, load_yaml


class LayerLoadError(ValueError):
    """Raised when an exposure/vulnerability source layer is missing or invalid."""


def exposure_vulnerability_dir(exposure_cfg: dict[str, Any] | None = None) -> Path:
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    return PROJECT_ROOT / exposure_cfg["output_dir"]


def load_layer(filename: str, exposure_cfg: dict[str, Any] | None = None) -> np.ndarray:
    """Read one band from an already-acquired exposure/vulnerability GeoTIFF."""
    path = exposure_vulnerability_dir(exposure_cfg) / filename
    if not path.exists():
        raise LayerLoadError(
            f"No such layer: {path}. Run "
            f"scripts/02_download_exposure_vulnerability_data.py to build it."
        )
    with rasterio.open(path) as src:
        return src.read(1).astype("float64")


def robust_percentile_normalize(
    array: np.ndarray, p_low: float = 5, p_high: float = 95, invert: bool = False
) -> np.ndarray:
    """Scale `array` to [0, 1] using the p_low/p_high percentiles (computed
    over valid, non-NaN cells) as the clipping bounds. NaN cells stay NaN.

    Robust to outliers unlike min-max (methodology.md's normalization
    convention for both exposure and vulnerability layers). If invert=True,
    returns 1 - normalized (for a beneficial/capacity-framed raw indicator
    that needs to become "higher = more vulnerable").
    """
    valid = array[np.isfinite(array)]
    if valid.size == 0:
        return np.full_like(array, np.nan, dtype="float64")

    lo, hi = np.percentile(valid, [p_low, p_high])
    if hi <= lo:
        # degenerate case: indicator has (near-)zero variation in this domain
        result = np.where(np.isfinite(array), 0.5, np.nan)
    else:
        clipped = np.clip(array, lo, hi)
        result = (clipped - lo) / (hi - lo)
        result = np.where(np.isfinite(array), result, np.nan)

    if invert:
        result = np.where(np.isfinite(result), 1.0 - result, np.nan)

    return result


def ethiopia_admin0_mask(domain_cfg: dict[str, Any] | None = None) -> np.ndarray:
    """Boolean array (True = inside Ethiopia's national boundary) on the
    analysis grid, used as the target footprint for gap-filling.
    """
    from hydroclim_risk.acquisition.common import analysis_grid_transform_and_shape
    from hydroclim_risk.ingestion.boundaries import load_admin_boundaries

    domain_cfg = domain_cfg or load_data_config()
    transform, height, width = analysis_grid_transform_and_shape(domain_cfg)
    admin0 = load_admin_boundaries(0).to_crs(domain_cfg["domain"]["crs"])

    from rasterio.features import geometry_mask

    return geometry_mask(admin0.geometry, out_shape=(height, width), transform=transform, invert=True)


def fill_gaps_nearest_neighbor(array: np.ndarray, target_mask: np.ndarray) -> np.ndarray:
    """Fill NaN cells that fall within `target_mask` using the value of the
    nearest valid (non-NaN) cell in `array` (Euclidean nearest-neighbor).
    Cells outside target_mask are left untouched even if NaN -- this is for
    filling real data gaps within a domain of interest (e.g. Ethiopia),
    not for extending coverage beyond it.

    Meant for real, spatially-clustered data gaps (e.g. a source dataset
    that's missing coverage for part of the country) where nearby cells are
    a defensible proxy -- not a substitute for actually-missing indicators.
    """
    valid = np.isfinite(array)
    if valid.all():
        return array.copy()
    if not valid.any():
        return array.copy()  # nothing to fill from

    _, indices = distance_transform_edt(~valid, return_distances=True, return_indices=True)
    nearest_values = array[tuple(indices)]

    result = array.copy()
    needs_fill = ~valid & target_mask
    result[needs_fill] = nearest_values[needs_fill]
    return result
