"""Load per-member (realization-preserving) indicator NetCDFs from
outputs/netcdf/ — delivered 2026-07-24 by the sibling extremes-climate-indices
pipeline on request, to support hazard-probability calculation (P_drought =
count(H_dry >= threshold) / 25, which needs member-level hazard scores, not
an already-collapsed ensemble mean/median).

Six indicators, one file per period: rainfall percentile, SPI, and CDD/CWD/
Rx1day/Rx5day percentile-rank. All share dims (lat, lon, realization=25) and
the same Ethiopia boundary mask as the rest of outputs/geotiff/.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import xarray as xr

from hydroclim_risk.config import PROJECT_ROOT, load_data_config, load_thresholds_config
from hydroclim_risk.ingestion.netcdf import GridValidationError, validate_grid

_FILENAME_RE = re.compile(r"^ethiopia_(?P<period>[A-Za-z]+)_(?P<init_date>[\d-]+)_(?P<token>.+)_members\.nc$")

# indicator name (matching the vocabulary used by ingestion.geotiff) -> filename token
_INDICATOR_TOKENS = {
    "percentile": "percentile",  # rainfall percentile
    "spi": "spi",
    "cdd": "cdd_percentile",
    "cwd": "cwd_percentile",
    "rx1day": "rx1day_percentile",
    "rx5day": "rx5day_percentile",
}
_TOKEN_TO_INDICATOR = {token: indicator for indicator, token in _INDICATOR_TOKENS.items()}


class MembersLoadError(ValueError):
    """Raised for missing files, unparseable names, or an unexpected member count."""


def _members_dir(cfg: dict[str, Any] | None) -> Path:
    cfg = cfg or load_data_config()
    return PROJECT_ROOT / cfg["paths"]["netcdf_members_dir"]


def parse_filename(filename: str) -> dict[str, str]:
    m = _FILENAME_RE.match(filename)
    if not m:
        raise MembersLoadError(f"Filename does not match expected pattern: {filename}")
    token = m.group("token")
    if token not in _TOKEN_TO_INDICATOR:
        raise MembersLoadError(f"Unrecognized indicator token {token!r} in: {filename}")
    return {
        "period": m.group("period"),
        "init_date": m.group("init_date"),
        "indicator": _TOKEN_TO_INDICATOR[token],
    }


def build_filename(period: str, indicator: str, init_date: str) -> str:
    if indicator not in _INDICATOR_TOKENS:
        raise ValueError(f"indicator must be one of {sorted(_INDICATOR_TOKENS)}, got {indicator!r}")
    return f"ethiopia_{period}_{init_date}_{_INDICATOR_TOKENS[indicator]}_members.nc"


def _cap_spi(da: xr.DataArray, cap: float) -> xr.DataArray:
    capped = da.clip(min=-cap, max=cap)
    capped.attrs = {**da.attrs, "spi_cap_applied": cap}
    return capped


def load_member_indicator(
    period: str,
    indicator: str,
    init_date: str = "2026-05-01",
    apply_spi_cap: bool = True,
    cfg: dict[str, Any] | None = None,
    thresholds_cfg: dict[str, Any] | None = None,
) -> xr.DataArray:
    """Load one indicator's per-member DataArray, dims (lat, lon, realization=25).

    Validates grid alignment (via ingestion.netcdf.validate_grid) and the
    25-member count. SPI is capped at thresholds.yaml's spi.cap_abs_value by
    default, same as ingestion.geotiff.load_indicator.
    """
    cfg = cfg or load_data_config()
    filename = build_filename(period, indicator, init_date)
    path = _members_dir(cfg) / filename
    if not path.exists():
        raise MembersLoadError(f"No such member-level indicator NetCDF: {path}")

    ds = xr.open_dataset(path, decode_timedelta=False)
    var_names = list(ds.data_vars)
    if len(var_names) != 1:
        raise MembersLoadError(f"Expected exactly 1 data variable in {path}, found {var_names}")
    da = ds[var_names[0]]

    validate_grid(da, cfg)

    expected_members = cfg["ensemble"]["forecast_member_count"]
    if da.sizes.get("realization") != expected_members:
        raise GridValidationError(
            f"{path} has {da.sizes.get('realization')} realization members, expected "
            f"{expected_members}."
        )

    da.attrs = {**da.attrs, "period": period, "indicator": indicator}

    if apply_spi_cap and indicator == "spi":
        thresholds_cfg = thresholds_cfg or load_thresholds_config()
        cap = float(thresholds_cfg["spi"]["cap_abs_value"])
        da = _cap_spi(da, cap)

    return da
