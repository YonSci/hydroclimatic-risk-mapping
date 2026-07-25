from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.config import load_data_config, load_yaml
from hydroclim_risk.layers import (
    LayerLoadError,
    ethiopia_admin0_mask,
    fill_gaps_nearest_neighbor,
    load_layer,
    robust_percentile_normalize,
)

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def test_load_layer_reads_values(tmp_path: Path):
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path)

    transform = Affine(DOMAIN["resolution_deg"], 0, DOMAIN["lon_min"], 0, -DOMAIN["resolution_deg"], DOMAIN["lat_max"])
    with rasterio.open(
        tmp_path / "test.tif", "w", driver="GTiff", height=4, width=5, count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(np.full((4, 5), 9.0), 1)

    result = load_layer("test.tif", cfg)
    np.testing.assert_allclose(result, 9.0)


def test_load_layer_missing_raises_layer_load_error(tmp_path: Path):
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path)
    with pytest.raises(LayerLoadError):
        load_layer("nope.tif", cfg)


def test_robust_percentile_normalize_basic():
    array = np.arange(101, dtype="float64")
    result = robust_percentile_normalize(array, p_low=5, p_high=95)
    assert result.min() == 0.0
    assert result.max() == 1.0


def test_fill_gaps_nearest_neighbor_fills_only_within_target_mask():
    array = np.array(
        [[1.0, np.nan, 3.0],
         [np.nan, np.nan, np.nan],
         [7.0, 8.0, np.nan]]
    )
    # only the middle row and (2,2) are "of interest" -- top-right (0,1) NaN
    # is outside the target mask and must stay NaN
    target_mask = np.array(
        [[False, False, False],
         [True, True, True],
         [False, False, True]]
    )
    result = fill_gaps_nearest_neighbor(array, target_mask)

    assert np.isnan(result[0, 1])  # outside target mask -> untouched
    assert not np.isnan(result[1, 0])  # inside target mask -> filled
    assert not np.isnan(result[1, 1])
    assert not np.isnan(result[1, 2])
    assert not np.isnan(result[2, 2])
    # originally-valid cells must be unchanged
    assert result[0, 0] == 1.0
    assert result[2, 0] == 7.0


def test_fill_gaps_nearest_neighbor_no_gaps_returns_copy():
    array = np.array([[1.0, 2.0], [3.0, 4.0]])
    mask = np.full((2, 2), True)
    result = fill_gaps_nearest_neighbor(array, mask)
    np.testing.assert_array_equal(result, array)
    assert result is not array


def test_fill_gaps_nearest_neighbor_uses_nearest_not_just_any_valid_cell():
    # a 1D-like strip: valid values 10 at col 0, 20 at col 4 -> col 1 should
    # take 10 (nearer), col 3 should take 20 (nearer)
    array = np.array([[10.0, np.nan, np.nan, np.nan, 20.0]])
    mask = np.full(array.shape, True)
    result = fill_gaps_nearest_neighbor(array, mask)
    assert result[0, 1] == 10.0
    assert result[0, 3] == 20.0


def test_ethiopia_admin0_mask_matches_expected_cell_count():
    mask = ethiopia_admin0_mask(CFG)
    assert mask.dtype == bool
    assert mask.shape == tuple(DOMAIN["grid_shape"])
    # confirmed via direct rasterization earlier in this project (2026-07-25)
    assert mask.sum() == 1484
