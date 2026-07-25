from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from hydroclim_risk.config import load_data_config
from hydroclim_risk.export.mapping import preview_geotiff, save_png_preview

CFG = load_data_config()
DOMAIN = CFG["domain"]


def test_save_png_preview_creates_a_nonempty_file(tmp_path: Path):
    shape = tuple(DOMAIN["grid_shape"])
    array = np.random.default_rng(0).random(shape)
    dest = tmp_path / "preview.png"

    result = save_png_preview(array, dest, title="test", show_admin0_boundary=False)

    assert result == dest
    assert dest.exists()
    assert dest.stat().st_size > 0
    with open(dest, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_save_png_preview_handles_all_nan_array(tmp_path: Path):
    shape = tuple(DOMAIN["grid_shape"])
    array = np.full(shape, np.nan)
    dest = tmp_path / "allnan.png"
    result = save_png_preview(array, dest, show_admin0_boundary=False)
    assert result.exists()


def test_save_png_preview_with_admin0_boundary_overlay(tmp_path: Path):
    # exercises the real boundary-loading code path
    shape = tuple(DOMAIN["grid_shape"])
    array = np.random.default_rng(0).random(shape)
    dest = tmp_path / "with_boundary.png"
    result = save_png_preview(array, dest, domain_cfg=CFG, show_admin0_boundary=True)
    assert result.exists()
    assert result.stat().st_size > 0


def _write_tif(path: Path, arr: np.ndarray):
    transform = Affine(DOMAIN["resolution_deg"], 0, DOMAIN["lon_min"], 0, -DOMAIN["resolution_deg"], DOMAIN["lat_max"])
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(arr, 1)


def test_preview_geotiff_default_output_path(tmp_path: Path, monkeypatch):
    src_tif = tmp_path / "raw" / "my_layer.tif"
    src_tif.parent.mkdir()
    _write_tif(src_tif, np.random.default_rng(0).random(tuple(DOMAIN["grid_shape"])))

    out_dir = tmp_path / "figs"
    result = preview_geotiff(src_tif, output_dir=out_dir, show_admin0_boundary=False)

    assert result == out_dir / "my_layer.png"
    assert result.exists()


def test_preview_geotiff_explicit_dest_path(tmp_path: Path):
    src_tif = tmp_path / "my_layer.tif"
    _write_tif(src_tif, np.random.default_rng(0).random(tuple(DOMAIN["grid_shape"])))

    dest = tmp_path / "custom_name.png"
    result = preview_geotiff(src_tif, dest_path=dest, show_admin0_boundary=False)

    assert result == dest
    assert dest.exists()
