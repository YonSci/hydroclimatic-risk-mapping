from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

from hydroclim_risk.acquisition.poverty import download_poverty
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def test_download_poverty_bins_points_correctly(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    # two points fall in the same output cell (row 0, col 0) -> mean expected
    # one point falls in a distinct, known cell
    df = pd.DataFrame({
        "latitude": [14.9, 14.8, 10.0],
        "longitude": [33.1, 33.2, 40.0],
        "rwi": [1.0, 3.0, 5.0],
        "error": [0.1, 0.1, 0.1],
    })

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(dest_path, index=False)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.poverty.download_file", fake_download_file)

    dest = download_poverty(exposure_cfg=cfg)
    assert dest.exists()

    with rasterio.open(dest) as src:
        grid = src.read(1)
        tags = src.tags()

    assert tags["source"] == "meta_rwi"
    assert tags["variable"] == "relative_wealth_index"

    assert grid[0, 0] == pytest.approx(2.0)  # mean of 1.0 and 3.0

    col = int(round((40.0 - DOMAIN["lon_min"]) / DOMAIN["resolution_deg"]))
    row = int(round((DOMAIN["lat_max"] - 10.0) / DOMAIN["resolution_deg"]))
    assert grid[row, col] == pytest.approx(5.0)

    # a cell with no points should be NaN, not 0
    n_non_nan = np.sum(~np.isnan(grid))
    assert n_non_nan == 2  # only the two distinct occupied cells


def test_download_poverty_handles_out_of_bounds_points(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)
    df = pd.DataFrame({
        "latitude": [50.0],  # far outside Ethiopia's domain
        "longitude": [33.1],
        "rwi": [9.9],
    })

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(dest_path, index=False)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.poverty.download_file", fake_download_file)

    dest = download_poverty(exposure_cfg=cfg)
    with rasterio.open(dest) as src:
        grid = src.read(1)
    assert np.all(np.isnan(grid))  # the one point is out of bounds -> nothing gridded
