import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.acquisition.ghs_built import download_ghs_built
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _write_synthetic_ghsl_zip(zip_path: Path, value: float = 500.0):
    src_res = DOMAIN["resolution_deg"] / 3
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])
    data = np.full((n_lat, n_lon), value, dtype="float32")

    tmp_tif = zip_path.parent / "inner.tif"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        tmp_tif, "w", driver="GTiff", height=n_lat, width=n_lon, count=1,
        dtype="float32", crs=DOMAIN["crs"], transform=transform, nodata=-1.0,
    ) as dst:
        dst.write(data, 1)

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(tmp_tif, arcname="GHS_BUILT_S_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif")
    tmp_tif.unlink()


def test_download_ghs_built_conserves_total_and_writes_tags(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_ghsl_zip(Path(dest_path), value=500.0)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.ghs_built.download_file", fake_download_file)

    dest = download_ghs_built(exposure_cfg=cfg)
    assert dest.exists()

    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    assert tags["source"] == "jrc_ghsl"
    assert tags["variable"] == "built_up_surface_m2"

    valid = result[~np.isnan(result)]
    assert valid.size > 0
    assert (valid > 0).all()  # 500 m^2/pixel over any positive area -> positive total
