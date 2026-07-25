"""Load raw exposure GeoTIFFs and derive computed indicators (currently:
irrigated/rainfed cropland split) for the exposure module.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hydroclim_risk.layers import LayerLoadError, ethiopia_admin0_mask, fill_gaps_nearest_neighbor, load_layer

ExposureLoadError = LayerLoadError


def cropland_irrigated(exposure_cfg: dict[str, Any] | None = None) -> np.ndarray:
    """Fraction of each cell that is irrigated cropland:
    cropland_fraction * (irrigation_percent / 100).

    methodology.md lists rainfed and irrigated cropland as separate mandatory
    exposure maps; GMIA's irrigated-area-% layer lets us split the single
    ESA WorldCover cropland_fraction layer into the two.
    """
    cropland = load_layer("ethiopia_cropland.tif", exposure_cfg)
    irrigation_pct = load_layer("ethiopia_irrigation_gmia.tif", exposure_cfg)
    return cropland * np.clip(irrigation_pct / 100.0, 0.0, 1.0)


def cropland_rainfed(exposure_cfg: dict[str, Any] | None = None) -> np.ndarray:
    """Fraction of each cell that is rainfed cropland:
    cropland_fraction * (1 - irrigation_percent / 100).
    """
    cropland = load_layer("ethiopia_cropland.tif", exposure_cfg)
    irrigation_pct = load_layer("ethiopia_irrigation_gmia.tif", exposure_cfg)
    return cropland * (1.0 - np.clip(irrigation_pct / 100.0, 0.0, 1.0))


_DERIVED_INDICATORS = {
    "cropland_irrigated": cropland_irrigated,
    "cropland_rainfed": cropland_rainfed,
}


def load_indicator(
    indicator_name: str,
    indicator_cfg: dict[str, Any],
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
) -> np.ndarray:
    """Load one exposure indicator's raw (absolute) array, whether it's a
    direct GeoTIFF layer or a derived quantity registered in
    _DERIVED_INDICATORS. A direct layer with `fill_gaps: true` in its config
    is nearest-neighbor gap-filled within Ethiopia's boundary (see
    config/exposure_indicators.yaml).
    """
    if indicator_cfg.get("derived"):
        if indicator_name not in _DERIVED_INDICATORS:
            raise ExposureLoadError(f"No derivation function registered for '{indicator_name}'")
        return _DERIVED_INDICATORS[indicator_name](exposure_cfg)

    array = load_layer(indicator_cfg["source_file"], exposure_cfg)
    if indicator_cfg.get("fill_gaps"):
        array = fill_gaps_nearest_neighbor(array, ethiopia_admin0_mask(domain_cfg))
    return array
