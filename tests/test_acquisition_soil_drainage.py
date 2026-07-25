from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from hydroclim_risk.acquisition.soil_drainage import download_soil_drainage
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _write_synthetic_clay_source(path: Path, clay_raw_value: float, nodata_fraction_cols: int = 0):
    # already EPSG:4326 (not Homolosine) -- WarpedVRT's reprojection becomes
    # a no-op identity warp, so this exercises the rest of the pipeline
    # (windowed decimated read, transform correction, nodata handling,
    # scale factor) without needing a real Homolosine test fixture.
    res = DOMAIN["resolution_deg"] / 8
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / res)) + 4
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / res)) + 4
    transform = Affine(res, 0, DOMAIN["lon_min"] - 2 * res, 0, -res, DOMAIN["lat_max"] + 2 * res)

    array = np.full((n_lat, n_lon), clay_raw_value, dtype="int16")
    if nodata_fraction_cols:
        array[:, :nodata_fraction_cols] = -32768  # simulate a real nodata gap (e.g. water) on the west edge

    with rasterio.open(
        path, "w", driver="GTiff", height=n_lat, width=n_lon, count=1,
        dtype="int16", crs="EPSG:4326", transform=transform, nodata=-32768,
    ) as dst:
        dst.write(array, 1)


def test_download_soil_drainage_applies_scale_factor_and_writes_layer(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)
    cfg["datasets"] = {**REAL_EXPOSURE_CFG["datasets"]}
    src_path = tmp_path / "synthetic_clay.tif"
    _write_synthetic_clay_source(src_path, clay_raw_value=300.0)  # -> 30.0 percent after scaling
    cfg["datasets"] = {
        **cfg["datasets"],
        "soil_drainage": {**cfg["datasets"]["soil_drainage"], "vrt_url": str(src_path)},
    }

    dest = download_soil_drainage(exposure_cfg=cfg)

    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    valid = result[np.isfinite(result)]
    assert valid.size == result.size  # full synthetic coverage, no gaps
    np.testing.assert_allclose(valid, 30.0, rtol=1e-6)
    assert tags["variable"] == "clay_content_percent"
    assert tags["source"] == "isric_soilgrids"
    assert tags["scale_factor_applied"] == "0.1"


def test_download_soil_drainage_excludes_nodata_from_averaging(tmp_path: Path, monkeypatch):
    # regression test for the found-2026-07-25 bug: omitting src_nodata during
    # the final reproject silently propagated NaN into nearly every output
    # cell whenever the source had real nodata gaps within the domain window
    cfg = _cfg_with_tmp_dirs(tmp_path)
    src_path = tmp_path / "synthetic_clay_with_gap.tif"
    _write_synthetic_clay_source(src_path, clay_raw_value=300.0, nodata_fraction_cols=6)
    cfg["datasets"] = {
        **REAL_EXPOSURE_CFG["datasets"],
        "soil_drainage": {**REAL_EXPOSURE_CFG["datasets"]["soil_drainage"], "vrt_url": str(src_path)},
    }

    dest = download_soil_drainage(exposure_cfg=cfg)

    with rasterio.open(dest) as src:
        result = src.read(1)

    valid = result[np.isfinite(result)]
    # most of the grid must still be valid (30.0), not wiped out by the small nodata strip
    assert valid.size > 0.8 * result.size
    np.testing.assert_allclose(valid, 30.0, rtol=1e-6)
