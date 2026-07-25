from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from hydroclim_risk.config import load_data_config
from hydroclim_risk.ingestion.netcdf import (
    GridValidationError,
    load_forecast_precip,
    load_historical_precip,
    validate_grid,
)

REAL_CFG = load_data_config()
DOMAIN = REAL_CFG["domain"]


def _make_grid_coords():
    res = DOMAIN["resolution_deg"]
    lat = np.round(
        np.arange(DOMAIN["lat_min"] + res / 2, DOMAIN["lat_max"], res), 6
    ).astype("float32")
    lon = np.round(
        np.arange(DOMAIN["lon_min"] + res / 2, DOMAIN["lon_max"], res), 6
    ).astype("float32")
    return lat, lon


def _make_synthetic_ds(n_time: int, n_realization: int) -> xr.Dataset:
    lat, lon = _make_grid_coords()
    time = pd.date_range("2020-05-02", periods=n_time, freq="D")
    rng = np.random.default_rng(0)
    data = rng.random((lat.size, lon.size, n_time, n_realization)).astype("float32")
    da = xr.DataArray(
        data,
        dims=("lat", "lon", "time", "realization"),
        coords={
            "lat": ("lat", lat, {"units": "degrees_north"}),
            "lon": ("lon", lon, {"units": "degrees_east"}),
            "time": time,
            "realization": np.arange(n_realization),
        },
        name="pr",
    )
    return da.to_dataset()


def _cfg_with_paths(**overrides) -> dict:
    cfg = {k: v for k, v in REAL_CFG.items()}
    cfg["paths"] = {**REAL_CFG["paths"], **overrides}
    return cfg


def test_synthetic_grid_matches_domain_by_construction(tmp_path: Path):
    ds = _make_synthetic_ds(n_time=3, n_realization=5)
    validate_grid(ds["pr"])  # should not raise


def test_load_historical_precip_slices_to_first_25(tmp_path: Path):
    ds = _make_synthetic_ds(n_time=4, n_realization=51)
    nc_path = tmp_path / "historical.nc"
    ds.to_netcdf(nc_path)

    cfg = _cfg_with_paths(historical_nc=str(nc_path))
    da = load_historical_precip(cfg=cfg)

    assert da.sizes["realization"] == 25
    assert list(da["realization"].values) == list(range(25))


def test_load_historical_precip_without_slice_keeps_all_members(tmp_path: Path):
    ds = _make_synthetic_ds(n_time=4, n_realization=51)
    nc_path = tmp_path / "historical.nc"
    ds.to_netcdf(nc_path)

    cfg = _cfg_with_paths(historical_nc=str(nc_path))
    da = load_historical_precip(apply_realization_slice=False, cfg=cfg)

    assert da.sizes["realization"] == 51


def test_load_forecast_precip_requires_25_members(tmp_path: Path):
    ds = _make_synthetic_ds(n_time=4, n_realization=20)  # wrong member count
    nc_path = tmp_path / "forecast.nc"
    ds.to_netcdf(nc_path)

    cfg = _cfg_with_paths(forecast_nc=str(nc_path))
    with pytest.raises(GridValidationError, match="25"):
        load_forecast_precip(cfg=cfg)


def test_load_forecast_precip_accepts_25_members(tmp_path: Path):
    ds = _make_synthetic_ds(n_time=4, n_realization=25)
    nc_path = tmp_path / "forecast.nc"
    ds.to_netcdf(nc_path)

    cfg = _cfg_with_paths(forecast_nc=str(nc_path))
    da = load_forecast_precip(cfg=cfg)
    assert da.sizes["realization"] == 25


def test_validate_grid_rejects_wrong_resolution():
    lat = np.arange(3.0, 15.0, 0.5).astype("float32")  # 0.5 deg, not 0.25
    lon = np.arange(33.0, 48.0, 0.5).astype("float32")
    da = xr.DataArray(
        np.zeros((lat.size, lon.size)),
        dims=("lat", "lon"),
        coords={
            "lat": ("lat", lat, {"units": "degrees_north"}),
            "lon": ("lon", lon, {"units": "degrees_east"}),
        },
    )
    with pytest.raises(GridValidationError):
        validate_grid(da)


def test_validate_grid_rejects_missing_units():
    lat, lon = _make_grid_coords()
    da = xr.DataArray(
        np.zeros((lat.size, lon.size)),
        dims=("lat", "lon"),
        coords={"lat": lat, "lon": lon},  # no units attrs
    )
    with pytest.raises(GridValidationError, match="units"):
        validate_grid(da)
