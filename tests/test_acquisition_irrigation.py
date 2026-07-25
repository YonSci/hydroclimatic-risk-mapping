import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio

from hydroclim_risk.acquisition.irrigation import download_irrigation
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _write_synthetic_gmia_zip(zip_path: Path, value: float = 12.5):
    # ASCII grid exactly matching the analysis domain (60x48), no CRS (.prj) --
    # mirrors the real GMIA v5 .asc distribution
    ncols, nrows = DOMAIN["grid_shape"][1], DOMAIN["grid_shape"][0]
    header = (
        f"ncols {ncols}\n"
        f"nrows {nrows}\n"
        f"xllcorner {DOMAIN['lon_min']}\n"
        f"yllcorner {DOMAIN['lat_min']}\n"
        f"cellsize {DOMAIN['resolution_deg']}\n"
        f"NODATA_value -9999\n"
    )
    row = " ".join([str(value)] * ncols)
    body = "\n".join([row] * nrows)
    asc_content = header + body + "\n"

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("gmia_v5_aei_pct.asc", asc_content)


def test_download_irrigation_writes_output_with_tags(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_gmia_zip(Path(dest_path), value=12.5)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.irrigation.download_file", fake_download_file)

    dest = download_irrigation(exposure_cfg=cfg)
    assert dest.exists()

    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()

    assert tags["source"] == "fao_gmia_v5"
    assert tags["variable"] == "irrigated_area_percent"
    assert tags["assumed_crs"] == "EPSG:4326"

    valid = result[~np.isnan(result)]
    assert valid.size > 0
    np.testing.assert_allclose(valid, 12.5, rtol=1e-3)  # constant source -> constant result under averaging


def test_extract_asc_raises_when_zip_has_no_asc_file(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_path, "w") as zf:
            zf.writestr("readme.txt", "no grid here")
        return dest_path

    monkeypatch.setattr("hydroclim_risk.acquisition.irrigation.download_file", fake_download_file)

    with pytest.raises(Exception, match="No .asc file"):
        download_irrigation(exposure_cfg=cfg)
