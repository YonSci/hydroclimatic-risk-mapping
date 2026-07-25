"""Download Meta's Relative Wealth Index (RWI) point data for Ethiopia and
grid it onto the analysis grid via mean-of-points-per-cell binning.

Source verified 2026-07-24: direct, no-auth CSV download from HDX
(data.humdata.org/Data for Good at Meta), ~2.4km point resolution (lat, lon,
rwi columns). Higher RWI = wealthier = LESS vulnerable -- this module only
grids the raw index; inverting/normalizing it into a vulnerability
sensitivity score belongs to the vulnerability module, not acquisition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hydroclim_risk.acquisition.common import (
    AcquisitionError,
    analysis_grid_transform_and_shape,
    download_file,
    output_path,
    raw_cache_path,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    raise AcquisitionError(f"Could not find any of {candidates} in columns {list(df.columns)}")


def download_poverty(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, grid, and write the poverty (RWI) vulnerability layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    ds_cfg = exposure_cfg["datasets"]["poverty"]

    raw_path = raw_cache_path("meta_rwi_eth.csv", exposure_cfg)
    download_file(ds_cfg["csv_url"], raw_path, overwrite=overwrite)

    df = pd.read_csv(raw_path)
    lat_col = _find_column(df, ["latitude", "lat"])
    lon_col = _find_column(df, ["longitude", "lon"])
    rwi_col = _find_column(df, ["rwi"])

    domain_cfg = domain_cfg or load_data_config()
    transform, height, width = analysis_grid_transform_and_shape(domain_cfg)
    res = domain_cfg["domain"]["resolution_deg"]
    lon_min = domain_cfg["domain"]["lon_min"]
    lat_max = domain_cfg["domain"]["lat_max"]

    col_idx = np.floor((df[lon_col].to_numpy() - lon_min) / res).astype(int)
    row_idx = np.floor((lat_max - df[lat_col].to_numpy()) / res).astype(int)
    in_bounds = (row_idx >= 0) & (row_idx < height) & (col_idx >= 0) & (col_idx < width)

    sums = np.zeros((height, width))
    counts = np.zeros((height, width))
    np.add.at(sums, (row_idx[in_bounds], col_idx[in_bounds]), df[rwi_col].to_numpy()[in_bounds])
    np.add.at(counts, (row_idx[in_bounds], col_idx[in_bounds]), 1)

    with np.errstate(invalid="ignore", divide="ignore"):
        grid = np.where(counts > 0, sums / counts, np.nan)

    dest = output_path("poverty_rwi", exposure_cfg)
    write_grid_geotiff(
        grid,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "note": "higher RWI = wealthier = less vulnerable; not yet inverted/normalized",
        },
        cfg=domain_cfg,
    )
    return dest
