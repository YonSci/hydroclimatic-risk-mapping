from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.acquisition.livestock import download_livestock
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _write_synthetic_glw4_tif(path: Path, value: float = 5.0):
    src_res = DOMAIN["resolution_deg"] / 3
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])
    data = np.full((n_lat, n_lon), value, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=n_lat, width=n_lon, count=1,
        dtype="float32", crs=DOMAIN["crs"], transform=transform, nodata=-1.0,
    ) as dst:
        dst.write(data, 1)


def test_download_livestock_rejects_unknown_species(tmp_path: Path):
    cfg = _cfg_with_tmp_dirs(tmp_path)
    with pytest.raises(ValueError, match="species must be one of"):
        download_livestock("dragons", exposure_cfg=cfg)


def test_download_livestock_writes_output_with_tags(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_glw4_tif(Path(dest_path), value=8.0)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.livestock.download_file", fake_download_file)

    dest = download_livestock("cattle", exposure_cfg=cfg)
    assert dest.exists()
    assert dest.name == "ethiopia_livestock_cattle.tif"

    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    assert tags["species"] == "cattle"
    assert tags["source"] == "fao_glw4"
    assert tags["variable"] == "cattle_head_count"
    valid = result[~np.isnan(result)]
    assert valid.size > 0
    assert (valid > 0).all()  # density 8 head/km^2 over any positive area -> positive head count
