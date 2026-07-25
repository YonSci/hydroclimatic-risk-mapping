from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.acquisition import terrain
from hydroclim_risk.acquisition.terrain import _slope_degrees, download_terrain
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def test_slope_degrees_is_zero_for_flat_terrain():
    elevation = np.full((20, 20), 1000.0)
    transform = Affine(0.01, 0, 33.0, 0, -0.01, 15.0)
    slope = _slope_degrees(elevation, transform)
    np.testing.assert_allclose(slope, 0.0, atol=1e-9)


def test_slope_degrees_increases_with_steeper_gradient():
    transform = Affine(0.01, 0, 33.0, 0, -0.01, 15.0)
    gentle = np.tile(np.arange(20) * 1.0, (20, 1))  # 1m per pixel (~0.01deg, ~1.1km) -> gentle
    steep = np.tile(np.arange(20) * 100.0, (20, 1))  # 100m per pixel -> steep
    slope_gentle = _slope_degrees(gentle, transform)
    slope_steep = _slope_degrees(steep, transform)
    assert np.all(slope_steep > slope_gentle)


def _write_synthetic_etopo(path: Path):
    # a global-scale-labelled but domain-covering synthetic elevation grid,
    # with a known linear west-to-east ramp so elevation/slope outputs are checkable
    res = DOMAIN["resolution_deg"] / 4
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / res)) + 4
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / res)) + 4
    transform = Affine(res, 0, DOMAIN["lon_min"] - 2 * res, 0, -res, DOMAIN["lat_max"] + 2 * res)

    col_ramp = np.arange(n_lon) * 50.0  # 50m elevation increase per source pixel, west to east
    elevation = np.tile(col_ramp, (n_lat, 1))

    with rasterio.open(
        path, "w", driver="GTiff", height=n_lat, width=n_lon, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-99999.0,
    ) as dst:
        dst.write(elevation.astype("float32"), 1)


def test_download_terrain_writes_elevation_and_slope(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)
    etopo_path = tmp_path / "synthetic_etopo.tif"
    _write_synthetic_etopo(etopo_path)
    monkeypatch.setattr(terrain, "_ETOPO_URL", str(etopo_path))

    elevation_dest, slope_dest = download_terrain(exposure_cfg=cfg)

    with rasterio.open(elevation_dest) as src:
        elevation = src.read(1)
        elev_tags = src.tags()
    with rasterio.open(slope_dest) as src:
        slope = src.read(1)
        slope_tags = src.tags()

    assert elev_tags["variable"] == "elevation_m"
    assert elev_tags["source"] == "noaa_etopo2022"
    assert slope_tags["variable"] == "slope_degrees"

    valid_elev = elevation[np.isfinite(elevation)]
    assert valid_elev.size == elevation.size  # synthetic source has full coverage, no gaps
    # west-to-east ramp: easternmost column must be higher than westernmost
    assert np.nanmean(elevation[:, -1]) > np.nanmean(elevation[:, 0])

    valid_slope = slope[np.isfinite(slope)]
    assert valid_slope.size == slope.size
    assert np.all(valid_slope >= 0)
    # a constant west-east gradient should produce roughly uniform slope
    assert np.nanstd(valid_slope) < np.nanmean(valid_slope) + 1.0
