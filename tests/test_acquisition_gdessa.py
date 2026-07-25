from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from hydroclim_risk.acquisition.gdessa import download_gdessa
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _write_synthetic_gdessa_nc(path: Path):
    src_res = DOMAIN["resolution_deg"] / 3
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))

    # descending latitude, matching the real file's convention
    lats = DOMAIN["lat_max"] - src_res / 2 - np.arange(n_lat) * src_res
    lons = DOMAIN["lon_min"] + src_res / 2 + np.arange(n_lon) * src_res

    n_years = 7
    # a distinct constant value per year so the test can confirm the LATEST
    # (index 6, "2020") is the one actually used, not an earlier year
    data = np.stack([np.full((n_lat, n_lon), float(year_idx) + 1.0) for year_idx in range(n_years)])

    ds = xr.Dataset(
        {"Pop_no_access_per_km2": (("Time (Year)", "Latitude", "Longitude"), data)},
        coords={"Time (Year)": np.arange(1, n_years + 1), "Latitude": lats, "Longitude": lons},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)


def test_download_gdessa_uses_latest_year_and_conserves_total(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)
    nc_path = tmp_path / "raw" / "gdessa_noaccess_ssa_2014_2020.nc"
    _write_synthetic_gdessa_nc(nc_path)

    dest = download_gdessa(exposure_cfg=cfg)
    assert dest.exists()

    import rasterio

    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    assert tags["source"] == "iiasa_gdessa"
    assert tags["variable"] == "population_no_electricity_access"
    assert tags["year"] == "2020"

    valid = result[~np.isnan(result)]
    assert valid.size > 0
    assert (valid > 0).all()  # density 7.0 (last year) over positive area -> positive count
