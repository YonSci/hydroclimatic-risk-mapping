from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from hydroclim_risk.config import load_data_config, load_thresholds_config
from hydroclim_risk.ingestion.members import (
    MembersLoadError,
    build_filename,
    load_member_indicator,
    parse_filename,
)
from hydroclim_risk.ingestion.netcdf import GridValidationError

REAL_CFG = load_data_config()
DOMAIN = REAL_CFG["domain"]


def _make_grid_coords():
    res = DOMAIN["resolution_deg"]
    lat = np.round(np.arange(DOMAIN["lat_min"] + res / 2, DOMAIN["lat_max"], res), 6).astype("float32")
    lon = np.round(np.arange(DOMAIN["lon_min"] + res / 2, DOMAIN["lon_max"], res), 6).astype("float32")
    return lat, lon


def _make_synthetic_ds(var_name: str, n_realization: int, value: float = 50.0) -> xr.Dataset:
    lat, lon = _make_grid_coords()
    data = np.full((lat.size, lon.size, n_realization), value, dtype="float64")
    da = xr.DataArray(
        data,
        dims=("lat", "lon", "realization"),
        coords={
            "lat": ("lat", lat, {"units": "degrees_north"}),
            "lon": ("lon", lon, {"units": "degrees_east"}),
            "realization": np.arange(n_realization),
        },
        name=var_name,
    )
    return da.to_dataset()


def _cfg_with_members_dir(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_CFG.items()}
    cfg["paths"] = {**REAL_CFG["paths"], "netcdf_members_dir": str(tmp_path)}
    return cfg


@pytest.mark.parametrize(
    "filename,expected",
    [
        (
            "ethiopia_June_2026-05-01_percentile_members.nc",
            {"period": "June", "init_date": "2026-05-01", "indicator": "percentile"},
        ),
        (
            "ethiopia_JJAS_2026-05-01_spi_members.nc",
            {"period": "JJAS", "init_date": "2026-05-01", "indicator": "spi"},
        ),
        (
            "ethiopia_August_2026-05-01_cdd_percentile_members.nc",
            {"period": "August", "init_date": "2026-05-01", "indicator": "cdd"},
        ),
        (
            "ethiopia_July_2026-05-01_rx5day_percentile_members.nc",
            {"period": "July", "init_date": "2026-05-01", "indicator": "rx5day"},
        ),
    ],
)
def test_parse_filename(filename: str, expected: dict):
    assert parse_filename(filename) == expected


def test_parse_filename_rejects_garbage():
    with pytest.raises(MembersLoadError):
        parse_filename("not_a_matching_name.nc")


def test_build_filename_roundtrips_parse():
    for indicator in ["percentile", "spi", "cdd", "cwd", "rx1day", "rx5day"]:
        filename = build_filename("June", indicator, "2026-05-01")
        assert parse_filename(filename) == {
            "period": "June", "init_date": "2026-05-01", "indicator": indicator,
        }


def test_load_member_indicator_missing_file_raises(tmp_path: Path):
    cfg = _cfg_with_members_dir(tmp_path)
    with pytest.raises(MembersLoadError, match="No such"):
        load_member_indicator("June", "spi", cfg=cfg)


def test_load_member_indicator_reads_values(tmp_path: Path):
    ds = _make_synthetic_ds("cdd_percentile", n_realization=25, value=80.0)
    ds.to_netcdf(tmp_path / build_filename("June", "cdd", "2026-05-01"))
    cfg = _cfg_with_members_dir(tmp_path)

    da = load_member_indicator("June", "cdd", cfg=cfg)
    assert da.sizes["realization"] == 25
    assert float(da.values.max()) == pytest.approx(80.0)
    assert da.attrs["indicator"] == "cdd"


def test_load_member_indicator_rejects_wrong_member_count(tmp_path: Path):
    ds = _make_synthetic_ds("spi", n_realization=20, value=0.5)  # wrong count
    ds.to_netcdf(tmp_path / build_filename("June", "spi", "2026-05-01"))
    cfg = _cfg_with_members_dir(tmp_path)

    with pytest.raises(GridValidationError, match="25"):
        load_member_indicator("June", "spi", cfg=cfg)


def test_load_member_indicator_caps_spi(tmp_path: Path):
    lat, lon = _make_grid_coords()
    data = np.zeros((lat.size, lon.size, 25), dtype="float64")
    data[0, 0, 0] = 4.75
    data[0, 0, 1] = -4.75
    da = xr.DataArray(
        data, dims=("lat", "lon", "realization"),
        coords={
            "lat": ("lat", lat, {"units": "degrees_north"}),
            "lon": ("lon", lon, {"units": "degrees_east"}),
            "realization": np.arange(25),
        },
        name="spi",
    )
    da.to_dataset().to_netcdf(tmp_path / build_filename("June", "spi", "2026-05-01"))
    cfg = _cfg_with_members_dir(tmp_path)
    thresholds = load_thresholds_config()
    cap = thresholds["spi"]["cap_abs_value"]

    capped = load_member_indicator("June", "spi", cfg=cfg)
    assert float(capped.values.max()) == pytest.approx(cap)
    assert float(capped.values.min()) == pytest.approx(-cap)

    uncapped = load_member_indicator("June", "spi", apply_spi_cap=False, cfg=cfg)
    assert float(uncapped.values.max()) == pytest.approx(4.75)


@pytest.mark.parametrize("indicator", ["percentile", "spi", "cdd", "cwd", "rx1day", "rx5day"])
@pytest.mark.parametrize("period", ["June", "July", "August", "September", "JJAS"])
def test_real_member_files_load_with_correct_shape(indicator: str, period: str):
    da = load_member_indicator(period, indicator)
    assert da.sizes["realization"] == 25
    assert da.sizes["lat"] == DOMAIN["grid_shape"][0]
    assert da.sizes["lon"] == DOMAIN["grid_shape"][1]


def test_real_spi_members_nan_mask_identical_across_all_members():
    da = load_member_indicator("June", "spi", apply_spi_cap=False)
    values = da.values
    mask0 = np.isnan(values[:, :, 0])
    for i in range(1, values.shape[2]):
        assert np.array_equal(np.isnan(values[:, :, i]), mask0)
