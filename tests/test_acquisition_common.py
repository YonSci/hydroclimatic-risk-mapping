from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.enums import Resampling

from hydroclim_risk.acquisition.common import (
    AcquisitionError,
    analysis_grid_transform_and_shape,
    cell_area_km2,
    download_file,
    reproject_array_to_grid,
    reproject_path_to_grid,
    resample_count_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config

CFG = load_data_config()
DOMAIN = CFG["domain"]


def _mock_response(chunks: list[bytes]):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.iter_content = MagicMock(return_value=iter(chunks))
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_analysis_grid_transform_and_shape_matches_domain():
    transform, height, width = analysis_grid_transform_and_shape(CFG)
    assert height == DOMAIN["grid_shape"][0]
    assert width == DOMAIN["grid_shape"][1]
    assert transform.a == pytest.approx(DOMAIN["resolution_deg"])
    assert transform.e == pytest.approx(-DOMAIN["resolution_deg"])
    assert transform.c == pytest.approx(DOMAIN["lon_min"])
    assert transform.f == pytest.approx(DOMAIN["lat_max"])


def test_download_file_writes_content_and_caches(tmp_path: Path):
    dest = tmp_path / "sub" / "file.bin"
    with patch("hydroclim_risk.acquisition.common.requests.get", return_value=_mock_response([b"hello", b"world"])) as mock_get:
        result = download_file("https://example.invalid/file.bin", dest)
        assert result == dest
        assert dest.read_bytes() == b"helloworld"
        assert mock_get.call_count == 1

        # second call should hit the cache, not the network
        download_file("https://example.invalid/file.bin", dest)
        assert mock_get.call_count == 1


def test_download_file_overwrite_forces_redownload(tmp_path: Path):
    dest = tmp_path / "file.bin"
    dest.write_bytes(b"old")
    with patch("hydroclim_risk.acquisition.common.requests.get", return_value=_mock_response([b"new"])) as mock_get:
        download_file("https://example.invalid/file.bin", dest, overwrite=True)
        assert dest.read_bytes() == b"new"
        assert mock_get.call_count == 1


def test_download_file_raises_after_retries_exhausted(tmp_path: Path):
    import requests

    dest = tmp_path / "file.bin"
    with patch(
        "hydroclim_risk.acquisition.common.requests.get",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ), patch("hydroclim_risk.acquisition.common.time.sleep"):
        with pytest.raises(AcquisitionError):
            download_file("https://example.invalid/file.bin", dest)
    assert not dest.exists()


def test_reproject_array_to_grid_average_preserves_constant_value():
    # a fine source grid, exactly covering the analysis domain, all set to 5.0
    src_res = DOMAIN["resolution_deg"] / 4
    src_transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    src_array = np.full((n_lat, n_lon), 5.0, dtype="float64")

    result = reproject_array_to_grid(src_array, src_transform, DOMAIN["crs"], resampling=Resampling.average)
    assert result.shape == tuple(DOMAIN["grid_shape"])
    np.testing.assert_allclose(result, 5.0, rtol=1e-6)


def test_cell_area_km2_shrinks_with_latitude():
    # longitude spacing shrinks toward the poles -> cell area should too
    area_equator = cell_area_km2(0.0, 0.25)
    area_15n = cell_area_km2(15.0, 0.25)
    assert area_15n < area_equator
    assert area_15n / area_equator == pytest.approx(np.cos(np.radians(15.0)), rel=1e-6)


def test_resample_count_to_grid_conserves_total_when_source_is_density():
    # constant density field (mimics GLW4, already head/km^2) -> resampled
    # count total should match density * total analysis-grid area
    src_res = DOMAIN["resolution_deg"] / 4
    src_transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    density = np.full((n_lat, n_lon), 2.0, dtype="float64")  # 2 head/km^2 everywhere

    result = resample_count_to_grid(
        density, src_transform, DOMAIN["crs"], src_resolution_deg=src_res, is_density=True,
    )
    dst_transform, dst_height, dst_width = analysis_grid_transform_and_shape(CFG)
    dst_lats = np.array([(dst_transform * (0, r + 0.5))[1] for r in range(dst_height)])
    # one area value per row, times the number of columns -> total over all 2880 cells
    expected_total = np.sum(2.0 * cell_area_km2(dst_lats, DOMAIN["resolution_deg"])) * dst_width
    assert np.nansum(result) == pytest.approx(expected_total, rel=1e-6)


def test_resample_count_to_grid_conserves_total_when_source_is_raw_count():
    # per-pixel count field (mimics WorldPop) at 4x finer resolution than
    # the analysis grid -> total count after aggregation should match the
    # original total count almost exactly (same underlying geographic area)
    src_res = DOMAIN["resolution_deg"] / 4
    src_transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    counts = np.full((n_lat, n_lon), 10.0, dtype="float64")  # 10 people per source pixel

    result = resample_count_to_grid(
        counts, src_transform, DOMAIN["crs"], src_resolution_deg=src_res, is_density=False,
    )
    total_src = counts.sum()
    total_dst = np.nansum(result)
    assert total_dst == pytest.approx(total_src, rel=1e-3)


def test_reproject_path_to_grid_roundtrip(tmp_path: Path):
    transform, height, width = analysis_grid_transform_and_shape(CFG)
    src_path = tmp_path / "src.tif"
    data = np.arange(height * width, dtype="float64").reshape(height, width)
    with rasterio.open(
        src_path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(data, 1)

    result = reproject_path_to_grid(src_path, resampling=Resampling.nearest)
    assert result.shape == (height, width)
    np.testing.assert_allclose(result, data, rtol=1e-6)


def test_write_grid_geotiff_roundtrips_values_and_tags(tmp_path: Path):
    _, height, width = analysis_grid_transform_and_shape(CFG)
    array = np.random.default_rng(0).random((height, width))
    dest = tmp_path / "out.tif"

    write_grid_geotiff(array, dest, variable="test_var", tags={"license": "CC-BY 4.0"})

    with rasterio.open(dest) as src:
        assert src.tags()["variable"] == "test_var"
        assert src.tags()["license"] == "CC-BY 4.0"
        np.testing.assert_allclose(src.read(1), array)
