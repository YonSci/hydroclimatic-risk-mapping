"""Load the two bias-corrected precipitation NetCDFs and validate their grid.

See config/data.yaml for the domain/ensemble parameters this module enforces,
and references/project-context.md for why the historical file needs the
realization[0:25] slice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from hydroclim_risk.config import PROJECT_ROOT, load_data_config

_VAR_NAME = "pr"


class GridValidationError(ValueError):
    """Raised when an input NetCDF's grid does not match config/data.yaml."""


def _resolve_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def validate_grid(da: xr.DataArray, cfg: dict[str, Any] | None = None) -> None:
    """Assert lat/lon extent, resolution, and shape match config/data.yaml.

    Fails loudly on mismatch (quality-safeguards.md: verify alignment before
    combining layers) rather than silently proceeding with a misaligned grid.
    """
    cfg = cfg or load_data_config()
    domain = cfg["domain"]
    tol = domain["resolution_deg"] / 100  # float32 coord rounding tolerance

    lat, lon = da["lat"].values, da["lon"].values
    if lat.shape[0] != domain["grid_shape"][0] or lon.shape[0] != domain["grid_shape"][1]:
        raise GridValidationError(
            f"Grid shape {(lat.shape[0], lon.shape[0])} != expected "
            f"{tuple(domain['grid_shape'])}"
        )

    expected_lat_min = domain["lat_min"] + domain["resolution_deg"] / 2
    expected_lat_max = domain["lat_max"] - domain["resolution_deg"] / 2
    expected_lon_min = domain["lon_min"] + domain["resolution_deg"] / 2
    expected_lon_max = domain["lon_max"] - domain["resolution_deg"] / 2

    for label, actual, expected in [
        ("lat min", lat.min(), expected_lat_min),
        ("lat max", lat.max(), expected_lat_max),
        ("lon min", lon.min(), expected_lon_min),
        ("lon max", lon.max(), expected_lon_max),
    ]:
        if abs(float(actual) - expected) > tol:
            raise GridValidationError(
                f"{label} = {actual} does not match expected cell-centre value "
                f"{expected} (+/-{tol}) from config/data.yaml domain"
            )

    for name, coord in [("lat", lat), ("lon", lon)]:
        if coord.size > 1:
            diffs = np.diff(coord)
            if not np.allclose(diffs, diffs[0], atol=tol):
                raise GridValidationError(f"{name} coordinate is not uniformly spaced")
            if abs(abs(float(diffs[0])) - domain["resolution_deg"]) > tol:
                raise GridValidationError(
                    f"{name} resolution {abs(float(diffs[0]))} != expected "
                    f"{domain['resolution_deg']} from config/data.yaml"
                )

    for coord_name, expected_units in [("lat", "degrees_north"), ("lon", "degrees_east")]:
        units = da[coord_name].attrs.get("units")
        if units != expected_units:
            raise GridValidationError(
                f"{coord_name} units = {units!r}, expected {expected_units!r} "
                f"(implicit EPSG:4326/{domain['crs']} check)"
            )


def load_historical_precip(
    apply_realization_slice: bool = True, cfg: dict[str, Any] | None = None
) -> xr.DataArray:
    """Load `pr` from corrected_1993_2025.nc, dask-backed and grid-validated.

    By default slices realization to config/data.yaml's
    ensemble.historical_realization_slice (first 25 members only) so the
    historical ensemble size is uniform across 1993-2025 and matches the
    2026 forecast file — see [[data_ragged_ensemble]] memory / project
    decision from 2026-07-24.
    """
    cfg = cfg or load_data_config()
    path = _resolve_path(cfg["paths"]["historical_nc"])
    ds = xr.open_dataset(path, chunks="auto", decode_timedelta=False)
    da = ds[_VAR_NAME]
    validate_grid(da, cfg)

    if apply_realization_slice:
        lo, hi = cfg["ensemble"]["historical_realization_slice"]
        da = da.isel(realization=slice(lo, hi))

    return da


def load_forecast_precip(
    validate_member_count: bool = True, cfg: dict[str, Any] | None = None
) -> xr.DataArray:
    """Load `pr` from corrected_2026.nc, dask-backed and grid-validated.

    Asserts the full 25-member ensemble is present by default — composite
    hazard probability requires member-level values, not an ensemble mean
    (see references/project-context.md).
    """
    cfg = cfg or load_data_config()
    path = _resolve_path(cfg["paths"]["forecast_nc"])
    ds = xr.open_dataset(path, chunks="auto", decode_timedelta=False)
    da = ds[_VAR_NAME]
    validate_grid(da, cfg)

    if validate_member_count:
        expected = cfg["ensemble"]["forecast_member_count"]
        actual = da.sizes["realization"]
        if actual != expected:
            raise GridValidationError(
                f"corrected_2026.nc has {actual} realization members, expected "
                f"{expected}. Composite hazard probability requires the full "
                f"member-level ensemble, not a mean/median-only file."
            )

    return da
