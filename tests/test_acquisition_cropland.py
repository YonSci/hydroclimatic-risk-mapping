from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.acquisition.cropland import (
    _resample_one_tile,
    _tile_url,
    _tiles_covering_bbox,
)
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
EXPOSURE_CFG = load_yaml("exposure_data")
CROPLAND_CFG = EXPOSURE_CFG["datasets"]["cropland"]


def test_tiles_covering_bbox_matches_hand_computed_ethiopia_tiles():
    tiles = _tiles_covering_bbox(33.0, 48.0, 3.0, 15.0, tile_size_deg=3)
    lat_tags = sorted({t[0] for t in tiles})
    lon_tags = sorted({t[1] for t in tiles})
    assert lat_tags == ["N03", "N06", "N09", "N12"]
    assert lon_tags == ["E033", "E036", "E039", "E042", "E045"]
    assert len(tiles) == 4 * 5


def test_tiles_covering_bbox_handles_non_multiple_bounds():
    # a bbox not aligned to the tile grid should still be fully covered
    tiles = _tiles_covering_bbox(1.0, 4.0, -1.0, 2.0, tile_size_deg=3)
    lat_tags = sorted({t[0] for t in tiles})
    lon_tags = sorted({t[1] for t in tiles})
    assert lat_tags == ["N00", "S03"]  # covers -1 to 2 -> tiles S03(-3..0) and N00(0..3)
    assert lon_tags == ["E000", "E003"]  # covers 1 to 4 -> tiles E000(0..3) and E003(3..6)


def test_tile_url_matches_confirmed_s3_naming():
    url = _tile_url(CROPLAND_CFG, "N03", "E033")
    assert url == (
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
        "v200/2021/map/ESA_WorldCover_10m_2021_v200_N03E033_Map.tif"
    )


def _write_synthetic_tile(path: Path, lat_tag_deg: int, lon_tag_deg: int, size: int = 240):
    # alternating columns of cropland(40)/non-cropland(10) -> exact 0.5
    # fraction in every destination cell after averaging
    transform = Affine(3.0 / size, 0, lon_tag_deg, 0, -3.0 / size, lat_tag_deg + 3.0)
    data = np.where(np.arange(size)[None, :] % 2 == 0, 40, 10).astype("uint8")
    data = np.tile(data, (size, 1))
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="uint8", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(data, 1)


def test_resample_one_tile_classifies_and_averages(tmp_path: Path, monkeypatch):
    local_tile = tmp_path / "N12E045.tif"
    _write_synthetic_tile(local_tile, lat_tag_deg=12, lon_tag_deg=45, size=240)

    real_open = rasterio.open

    def fake_open(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith("/vsicurl/"):
            return real_open(local_tile)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("hydroclim_risk.acquisition.cropland.rasterio.open", fake_open)

    result = _resample_one_tile(
        "https://fake.invalid/tile.tif", decimated_side=240, cropland_class_value=40,
        domain_cfg=CFG, lat_tag="N12", lon_tag="E045", tile_size_deg=3,
    )

    assert result.shape == tuple(DOMAIN["grid_shape"])

    # N12E045 covers lon 45-48, lat 12-15 -> destination rows 0-11, cols 48-59
    footprint = result[0:12, 48:60]
    np.testing.assert_allclose(footprint, 0.5, rtol=1e-6)

    # everywhere else should be untouched (NaN)
    outside = result.copy()
    outside[0:12, 48:60] = np.nan
    assert np.all(np.isnan(outside))


def test_resample_one_tile_returns_none_for_missing_tile(monkeypatch):
    import rasterio.errors

    def fake_open(path, *args, **kwargs):
        raise rasterio.errors.RasterioIOError("404")

    monkeypatch.setattr("hydroclim_risk.acquisition.cropland.rasterio.open", fake_open)

    result = _resample_one_tile(
        "https://fake.invalid/does_not_exist.tif", decimated_side=240, cropland_class_value=40,
        domain_cfg=CFG, lat_tag="N12", lon_tag="E045", tile_size_deg=3,
    )
    assert result is None
