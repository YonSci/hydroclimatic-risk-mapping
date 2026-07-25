from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.config import load_data_config, load_yaml
from hydroclim_risk.exposure.indicators import (
    ExposureLoadError,
    cropland_irrigated,
    cropland_rainfed,
    load_indicator,
)

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_output(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path)
    return cfg


def _write_tif(path: Path, value: float, shape=(4, 5)):
    transform = Affine(DOMAIN["resolution_deg"], 0, DOMAIN["lon_min"], 0, -DOMAIN["resolution_deg"], DOMAIN["lat_max"])
    with rasterio.open(
        path, "w", driver="GTiff", height=shape[0], width=shape[1], count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(np.full(shape, value, dtype="float64"), 1)


def test_cropland_split_sums_to_total(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_tif(tmp_path / "ethiopia_cropland.tif", value=0.4)  # 40% of cell is cropland
    _write_tif(tmp_path / "ethiopia_irrigation_gmia.tif", value=25.0)  # 25% of that is irrigated

    irrigated = cropland_irrigated(cfg)
    rainfed = cropland_rainfed(cfg)

    np.testing.assert_allclose(irrigated, 0.4 * 0.25)
    np.testing.assert_allclose(rainfed, 0.4 * 0.75)
    np.testing.assert_allclose(irrigated + rainfed, 0.4)  # split must reconstruct the total


def test_cropland_split_clips_irrigation_percent_above_100(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_tif(tmp_path / "ethiopia_cropland.tif", value=0.5)
    _write_tif(tmp_path / "ethiopia_irrigation_gmia.tif", value=150.0)  # bad data: >100%

    irrigated = cropland_irrigated(cfg)
    rainfed = cropland_rainfed(cfg)
    np.testing.assert_allclose(irrigated, 0.5)  # clipped to 100% irrigated
    np.testing.assert_allclose(rainfed, 0.0)


def test_load_indicator_dispatches_direct_vs_derived(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_tif(tmp_path / "raw.tif", value=42.0)
    direct = load_indicator("anything", {"source_file": "raw.tif"}, cfg)
    np.testing.assert_allclose(direct, 42.0)

    _write_tif(tmp_path / "ethiopia_cropland.tif", value=0.2)
    _write_tif(tmp_path / "ethiopia_irrigation_gmia.tif", value=10.0)
    derived = load_indicator("cropland_irrigated", {"derived": True}, cfg)
    np.testing.assert_allclose(derived, 0.2 * 0.10)


def test_load_indicator_unknown_derived_raises(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    with pytest.raises(ExposureLoadError, match="No derivation function"):
        load_indicator("not_registered", {"derived": True}, cfg)
