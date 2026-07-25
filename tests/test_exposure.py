from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.config import load_data_config, load_yaml
from hydroclim_risk.exposure.exposure import (
    compute_all_exposure_layers,
    compute_exposure_layer,
    write_exposure_layer,
)

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")
REAL_EXPOSURE_INDICATORS_CFG = load_yaml("exposure_indicators")


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


def _write_all_sources(tmp_path: Path):
    _write_tif(tmp_path / "ethiopia_population.tif", value=500.0)
    _write_tif(tmp_path / "ethiopia_cropland.tif", value=0.3)
    _write_tif(tmp_path / "ethiopia_irrigation_gmia.tif", value=20.0)
    _write_tif(tmp_path / "ethiopia_livestock_cattle.tif", value=80.0)
    _write_tif(tmp_path / "ethiopia_buildings.tif", value=15.0)
    _write_tif(tmp_path / "ethiopia_roads.tif", value=12.0)
    _write_tif(tmp_path / "ethiopia_healthsites.tif", value=1.0)
    _write_tif(tmp_path / "ethiopia_ghs_built.tif", value=2000.0)


def test_compute_exposure_layer_direct(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_all_sources(tmp_path)

    layer = compute_exposure_layer("population", exposure_cfg=cfg)
    np.testing.assert_allclose(layer.absolute, 500.0)
    assert layer.sector == "population"
    assert layer.absolute_units == "people"
    # constant input -> degenerate normalization -> neutral 0.5 everywhere
    np.testing.assert_allclose(layer.normalized, 0.5)


def test_compute_exposure_layer_derived(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_all_sources(tmp_path)

    layer = compute_exposure_layer("cropland_irrigated", exposure_cfg=cfg)
    np.testing.assert_allclose(layer.absolute, 0.3 * 0.20)
    assert layer.sector == "agriculture"


def test_compute_exposure_layer_honors_per_layer_percentile_override(tmp_path: Path):
    # healthsites overrides p_low/p_high to (0, 99) because the domain-wide
    # (5, 95) default degenerates to a flat 0.5 for a 95%+-zero sparse layer
    cfg = _cfg_with_tmp_output(tmp_path)
    shape = (10, 10)
    arr = np.zeros(shape)
    arr[0, 0] = 100.0  # one dominant cell, matching the real Addis Ababa pattern
    _write_arr(tmp_path / "ethiopia_healthsites.tif", arr)

    layer = compute_exposure_layer("healthsites", exposure_cfg=cfg)
    # with the override, the normalization must NOT collapse to a flat 0.5:
    # the zero cells and the one nonzero cell must be distinguishable
    assert layer.normalized[0, 0] > layer.normalized[1, 1]
    assert not np.allclose(layer.normalized, 0.5)


def _write_arr(path: Path, arr: np.ndarray):
    transform = Affine(DOMAIN["resolution_deg"], 0, DOMAIN["lon_min"], 0, -DOMAIN["resolution_deg"], DOMAIN["lat_max"])
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(arr.astype("float64"), 1)


def test_compute_exposure_layer_unknown_name_raises(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    with pytest.raises(KeyError):
        compute_exposure_layer("not_a_real_layer", exposure_cfg=cfg)


def test_compute_all_exposure_layers_returns_every_registered_layer(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_all_sources(tmp_path)

    all_layers = compute_all_exposure_layers(exposure_cfg=cfg)
    assert set(all_layers) == set(REAL_EXPOSURE_INDICATORS_CFG["layers"])


def test_write_exposure_layer_writes_normalized_always_absolute_only_if_derived(tmp_path: Path):
    cfg = _cfg_with_tmp_output(tmp_path)
    _write_all_sources(tmp_path)
    out_dir = tmp_path / "out"

    direct_layer = compute_exposure_layer("population", exposure_cfg=cfg)
    direct_written = write_exposure_layer("population", direct_layer, domain_cfg=CFG, output_dir=out_dir)
    assert "normalized" in direct_written
    assert "absolute" not in direct_written  # raw file already exists from acquisition
    assert direct_written["normalized"].exists()

    derived_layer = compute_exposure_layer("cropland_irrigated", exposure_cfg=cfg)
    derived_written = write_exposure_layer("cropland_irrigated", derived_layer, domain_cfg=CFG, output_dir=out_dir)
    assert "normalized" in derived_written and "absolute" in derived_written
    assert derived_written["normalized"].exists()
    assert derived_written["absolute"].exists()

    with rasterio.open(derived_written["absolute"]) as src:
        result = src.read(1)
    np.testing.assert_allclose(result, 0.3 * 0.20)
