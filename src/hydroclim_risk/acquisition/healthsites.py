"""Download the Global Healthsites Mapping Project's Ethiopia health-facility
locations and grid them onto the analysis grid as a facility count per cell.

Source verified 2026-07-24: direct, no-auth CSV download from HDX
(data.humdata.org) -- a pre-extracted bulk mirror of healthsites.io's data.
The live healthsites.io API requires a free API key; this HDX mirror does
not. Columns are X (longitude), Y (latitude), plus many OSM health-facility
tags; some rows (way/relation geometries without a precomputed centroid)
have empty X/Y and are dropped before binning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hydroclim_risk.acquisition.common import (
    analysis_grid_transform_and_shape,
    download_file,
    output_path,
    raw_cache_path,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml


def download_healthsites(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, grid, and write the health-facility-count exposure layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    ds_cfg = exposure_cfg["datasets"]["healthsites"]

    raw_path = raw_cache_path("healthsites_eth.csv", exposure_cfg)
    download_file(ds_cfg["csv_url"], raw_path, overwrite=overwrite)

    df = pd.read_csv(raw_path)
    df = df.dropna(subset=["X", "Y"])

    domain_cfg = domain_cfg or load_data_config()
    _, height, width = analysis_grid_transform_and_shape(domain_cfg)
    domain = domain_cfg["domain"]
    res = domain["resolution_deg"]

    col_idx = np.floor((df["X"].to_numpy() - domain["lon_min"]) / res).astype(int)
    row_idx = np.floor((domain["lat_max"] - df["Y"].to_numpy()) / res).astype(int)
    in_bounds = (row_idx >= 0) & (row_idx < height) & (col_idx >= 0) & (col_idx < width)

    counts = np.zeros((height, width))
    np.add.at(counts, (row_idx[in_bounds], col_idx[in_bounds]), 1)

    dest = output_path("healthsites", exposure_cfg)
    write_grid_geotiff(
        counts,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
        },
        cfg=domain_cfg,
    )
    return dest
