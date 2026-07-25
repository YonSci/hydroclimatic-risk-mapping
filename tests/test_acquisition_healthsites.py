from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio

from hydroclim_risk.acquisition.healthsites import download_healthsites
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def test_download_healthsites_counts_points_and_drops_missing_coords(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    # 3 valid points in the same cell (row 0, col 0), 1 valid point elsewhere,
    # 1 row with missing X/Y that must be dropped, not counted as (0,0)
    df = pd.DataFrame({
        "X": [33.1, 33.15, 33.2, 40.0, None],
        "Y": [14.9, 14.85, 14.8, 10.0, None],
        "name": ["Clinic A", "Clinic B", "Clinic C", "Hospital D", "No Coords"],
    })

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(dest_path, index=False)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.healthsites.download_file", fake_download_file)

    dest = download_healthsites(exposure_cfg=cfg)
    with rasterio.open(dest) as src:
        grid = src.read(1)
        tags = src.tags()

    assert tags["source"] == "healthsites_io"
    assert tags["variable"] == "health_facility_count"

    assert grid[0, 0] == 3

    col = int(round((40.0 - DOMAIN["lon_min"]) / DOMAIN["resolution_deg"]))
    row = int(round((DOMAIN["lat_max"] - 10.0) / DOMAIN["resolution_deg"]))
    assert grid[row, col] == 1

    assert grid.sum() == 4  # the 5th row (missing coords) must not be counted anywhere


def test_download_healthsites_empty_cells_are_zero_not_nan(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)
    df = pd.DataFrame({"X": [33.1], "Y": [14.9], "name": ["Only One"]})

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(dest_path, index=False)
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.healthsites.download_file", fake_download_file)

    dest = download_healthsites(exposure_cfg=cfg)
    with rasterio.open(dest) as src:
        grid = src.read(1)

    # a "no facilities here" cell is a real 0, not missing data
    assert not np.any(np.isnan(grid))
    assert grid.sum() == 1
