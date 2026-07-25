import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.acquisition.aridity import download_aridity
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _write_synthetic_cgiar_zip(zip_path: Path, ai_value: float = 5000.0, scale: float | None = None):
    src_res = DOMAIN["resolution_deg"] / 3
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    ai_tif = zip_path.parent / "ai_v31_yr.tif"
    et0_tif = zip_path.parent / "et0_v31_yr.tif"  # decoy -- must NOT be picked

    for path, value in [(ai_tif, ai_value), (et0_tif, 999.0)]:
        with rasterio.open(
            path, "w", driver="GTiff", height=n_lat, width=n_lon, count=1,
            dtype="float32", crs=DOMAIN["crs"], transform=transform, nodata=-1.0,
        ) as dst:
            dst.write(np.full((n_lat, n_lon), value, dtype="float32"), 1)
            if scale is not None:
                dst.scales = (scale,)

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(ai_tif, arcname="Global-AI_ET0__annual_v3_1/ai_v31_yr.tif")
        zf.write(et0_tif, arcname="Global-AI_ET0__annual_v3_1/et0_v31_yr.tif")
    ai_tif.unlink()
    et0_tif.unlink()


def test_download_aridity_picks_ai_file_and_applies_fallback_scale(tmp_path: Path, monkeypatch):
    # no embedded GDAL scale tag (matches the real CGIAR-CSI file, verified
    # 2026-07-24) -> the documented 0.0001 fallback must be applied
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_cgiar_zip(Path(dest_path), ai_value=5000.0, scale=None)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.aridity.download_file", fake_download_file)

    dest = download_aridity(exposure_cfg=cfg)
    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    valid = result[~np.isnan(result)]
    # picked AI (5000 * 0.0001 = 0.5), not ET0 (999 * 0.0001 = 0.0999)
    np.testing.assert_allclose(valid, 0.5, rtol=1e-3)
    assert tags["source"] == "cgiar_csi"
    assert tags["variable"] == "aridity_index"
    assert tags["scale_factor_applied"] == "0.0001"


def test_download_aridity_prefers_embedded_scale_tag_over_fallback(tmp_path: Path, monkeypatch):
    # a real embedded GDAL scale tag, distinct from the 0.0001 fallback,
    # must win -- proves the code reads it rather than always hardcoding 0.0001
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_cgiar_zip(Path(dest_path), ai_value=5000.0, scale=0.00005)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.aridity.download_file", fake_download_file)

    dest = download_aridity(exposure_cfg=cfg)
    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    valid = result[~np.isnan(result)]
    np.testing.assert_allclose(valid, 0.25, rtol=1e-3)  # 5000 * 0.00005
    assert tags["scale_factor_applied"] == "5e-05"
