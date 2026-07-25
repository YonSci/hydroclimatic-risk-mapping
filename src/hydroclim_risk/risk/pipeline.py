"""End-to-end orchestration: member-level indicators -> hazard scores ->
probability/severity -> combine with (static) vulnerability and one exposure
sector -> risk, for a given forecast period.

Handles a subtle but critical alignment issue: ingestion.members' NetCDF
data has latitude ASCENDING (row 0 = south, the raw NetCDF/source
convention -- confirmed 2026-07-25), while exposure/vulnerability's
GeoTIFF-derived numpy arrays have latitude DESCENDING (row 0 = north,
matching every other GeoTIFF in outputs/ throughout this project).
P_drought/P_wet/S_drought/S_wet must be reoriented to north-up before
combining with E/V, or the resulting risk map would be spatially flipped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from hydroclim_risk.acquisition.common import write_grid_geotiff
from hydroclim_risk.config import PROJECT_ROOT, load_data_config
from hydroclim_risk.exposure import compute_exposure_layer
from hydroclim_risk.hazard import (
    cdd_dry_score,
    compute_h_dry,
    compute_h_wet,
    cwd_dry_score,
    cwd_wet_score,
    rainfall_percentile_dry_score,
    rainfall_percentile_wet_score,
    rx1day_wet_score,
    rx5day_wet_score,
    spi_dry_score,
    spi_wet_score,
)
from hydroclim_risk.ingestion.members import load_member_indicator
from hydroclim_risk.probability import compute_p_drought, compute_p_wet, compute_s_drought, compute_s_wet
from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code
from hydroclim_risk.vulnerability import compute_v_drought, compute_v_wet


def to_north_up(da: xr.DataArray) -> np.ndarray:
    """Reorder a (lat, lon[, ...]) DataArray to descending latitude
    (north-up, row 0 = north) and return plain numpy -- the convention used
    by every rasterio-derived array (exposure/, vulnerability/) in this
    project.
    """
    return da.sortby("lat", ascending=False).transpose("lat", "lon", ...).values


def compute_hazard_and_probability_for_period(
    period: str, init_date: str = "2026-05-01", apply_spi_cap: bool = True
) -> dict[str, np.ndarray]:
    """Load member-level indicators for `period`, compute H_dry/H_wet, then
    P_drought/P_wet/S_drought/S_wet -- returned as north-up numpy arrays.
    """
    rainfall_p = load_member_indicator(period, "percentile", init_date=init_date)
    spi = load_member_indicator(period, "spi", init_date=init_date, apply_spi_cap=apply_spi_cap)
    cdd_p = load_member_indicator(period, "cdd", init_date=init_date)
    cwd_p = load_member_indicator(period, "cwd", init_date=init_date)
    rx1_p = load_member_indicator(period, "rx1day", init_date=init_date)
    rx5_p = load_member_indicator(period, "rx5day", init_date=init_date)

    h_dry = compute_h_dry(
        {
            "spi_dry_score": spi_dry_score(spi),
            "rainfall_percentile_dry_score": rainfall_percentile_dry_score(rainfall_p),
            "cdd_dry_score": cdd_dry_score(cdd_p),
            "cwd_dry_score": cwd_dry_score(cwd_p),
        }
    )
    h_wet = compute_h_wet(
        {
            "spi_wet_score": spi_wet_score(spi),
            "rainfall_percentile_wet_score": rainfall_percentile_wet_score(rainfall_p),
            "cwd_wet_score": cwd_wet_score(cwd_p),
            "rx1day_wet_score": rx1day_wet_score(rx1_p),
            "rx5day_wet_score": rx5day_wet_score(rx5_p),
        }
    )

    return {
        "p_drought": to_north_up(compute_p_drought(h_dry)),
        "p_wet": to_north_up(compute_p_wet(h_wet)),
        "s_drought": to_north_up(compute_s_drought(h_dry)),
        "s_wet": to_north_up(compute_s_wet(h_wet)),
    }


def compute_risk_for_period_and_sector(
    period: str,
    sector: str,
    init_date: str = "2026-05-01",
    domain_cfg: dict[str, Any] | None = None,
) -> dict[str, np.ndarray]:
    """Full R = 100*P*S*E*V pipeline for one forecast period and one
    exposure sector (see config/exposure_indicators.yaml for valid sector
    names). Vulnerability is static (not period-dependent); hazard/
    probability are period-specific.
    """
    domain_cfg = domain_cfg or load_data_config()

    hazard_prob = compute_hazard_and_probability_for_period(period, init_date=init_date)
    v_drought = compute_v_drought(domain_cfg=domain_cfg)
    v_wet = compute_v_wet(domain_cfg=domain_cfg)
    e_layer = compute_exposure_layer(sector, domain_cfg=domain_cfg)

    r_drought = compute_risk(hazard_prob["p_drought"], hazard_prob["s_drought"], e_layer.normalized, v_drought)
    r_wet = compute_risk(hazard_prob["p_wet"], hazard_prob["s_wet"], e_layer.normalized, v_wet)
    r_dominant = combine_dominant_risk(r_drought, r_wet)

    return {
        "r_drought": r_drought,
        "r_wet": r_wet,
        "r_dominant": r_dominant,
        "dominant_code": dominant_risk_code(r_drought, r_wet),
        "risk_class": classify_risk(r_dominant),
    }


def write_risk_layers(
    period: str,
    sector: str,
    risk_result: dict[str, np.ndarray],
    domain_cfg: dict[str, Any] | None = None,
    output_dir: Path | str = "outputs/risk",
    init_date: str = "2026-05-01",
) -> dict[str, Path]:
    """Write every array in risk_result (as returned by
    compute_risk_for_period_and_sector) to outputs/risk/ as a GeoTIFF,
    following the project's ethiopia_{period}_{init_date}_... naming
    convention used throughout outputs/.
    """
    domain_cfg = domain_cfg or load_data_config()
    out_dir = PROJECT_ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for product, array in risk_result.items():
        path = out_dir / f"ethiopia_{period}_{init_date}_{sector}_{product}.tif"
        write_grid_geotiff(
            array, path, variable=f"{sector}_{product}",
            tags={"period": period, "sector": sector, "product": product},
            cfg=domain_cfg,
        )
        written[product] = path
    return written
