"""Compute absolute + normalized (0-1) exposure layers per sector, per
methodology.md's Exposure section: keep sectors SEPARATE (population,
cropland, livestock, infrastructure...) -- never blended into one index
unless explicitly requested.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

from hydroclim_risk.acquisition.common import write_grid_geotiff
from hydroclim_risk.config import PROJECT_ROOT, load_data_config, load_yaml
from hydroclim_risk.exposure.indicators import load_indicator
from hydroclim_risk.layers import robust_percentile_normalize


class ExposureLayer(NamedTuple):
    absolute: np.ndarray
    normalized: np.ndarray
    absolute_units: str
    sector: str


def _load_exposure_indicators_config(exp_ind_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    return exp_ind_cfg or load_yaml("exposure_indicators")


def compute_exposure_layer(
    name: str,
    exp_ind_cfg: dict[str, Any] | None = None,
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
) -> ExposureLayer:
    exp_ind_cfg = _load_exposure_indicators_config(exp_ind_cfg)
    if name not in exp_ind_cfg["layers"]:
        raise KeyError(
            f"'{name}' is not registered in config/exposure_indicators.yaml; "
            f"choices: {sorted(exp_ind_cfg['layers'])}"
        )

    ind_cfg = exp_ind_cfg["layers"][name]
    norm_cfg = exp_ind_cfg["normalization"]
    # a layer may override the domain-wide p_low/p_high (e.g. healthsites --
    # see config/exposure_indicators.yaml's comment on sparse indicators)
    p_low = ind_cfg.get("p_low", norm_cfg["p_low"])
    p_high = ind_cfg.get("p_high", norm_cfg["p_high"])

    absolute = load_indicator(name, ind_cfg, exposure_cfg, domain_cfg)
    normalized = robust_percentile_normalize(absolute, p_low=p_low, p_high=p_high)

    return ExposureLayer(
        absolute=absolute, normalized=normalized, absolute_units=ind_cfg["absolute_units"], sector=ind_cfg["sector"]
    )


def compute_all_exposure_layers(
    exp_ind_cfg: dict[str, Any] | None = None,
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
) -> dict[str, ExposureLayer]:
    exp_ind_cfg = _load_exposure_indicators_config(exp_ind_cfg)
    return {
        name: compute_exposure_layer(name, exp_ind_cfg, exposure_cfg, domain_cfg) for name in exp_ind_cfg["layers"]
    }


def write_exposure_layer(
    name: str,
    layer: ExposureLayer,
    domain_cfg: dict[str, Any] | None = None,
    output_dir: Path | str = "outputs/exposure",
) -> dict[str, Path]:
    """Write the normalized layer (always) and, for derived indicators
    without their own acquisition-stage file (e.g. cropland_irrigated), the
    absolute layer too. Returns {"normalized": path} or {"normalized": path,
    "absolute": path}.
    """
    domain_cfg = domain_cfg or load_data_config()
    out_dir = PROJECT_ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}

    norm_path = out_dir / f"ethiopia_{name}_normalized.tif"
    write_grid_geotiff(
        layer.normalized, norm_path, variable=f"{name}_normalized",
        tags={"sector": layer.sector, "absolute_units": layer.absolute_units, "range": "0-1"},
        cfg=domain_cfg,
    )
    written["normalized"] = norm_path

    exp_ind_cfg = load_yaml("exposure_indicators")
    if exp_ind_cfg["layers"][name].get("derived"):
        abs_path = out_dir / f"ethiopia_{name}_absolute.tif"
        write_grid_geotiff(
            layer.absolute, abs_path, variable=name,
            tags={"sector": layer.sector, "units": layer.absolute_units},
            cfg=domain_cfg,
        )
        written["absolute"] = abs_path

    return written
