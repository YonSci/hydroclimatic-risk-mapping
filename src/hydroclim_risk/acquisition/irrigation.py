"""Download FAO/University of Bonn GMIA v5 (area equipped for irrigation, %
of total area) and resample it onto the analysis grid.

Source verified 2026-07-24: direct, no-auth ZIP download from FAO's Google
Cloud Storage mirror (storage.googleapis.com/fao-maps-catalog-data/...),
global ESRI ASCII-grid, 5 arcmin (~0.0833 deg) resolution. The .asc file
ships without an embedded CRS (no .prj) -- GMIA v5's documented spatial
reference is EPSG:4326 (WGS84 lat/lon), assumed explicitly below.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling

from hydroclim_risk.acquisition.common import (
    download_file,
    extract_single_file,
    output_path,
    raw_cache_path,
    reproject_array_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml

_ASSUMED_CRS = "EPSG:4326"


def download_irrigation(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, resample, and write the irrigation-access vulnerability layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    ds_cfg = exposure_cfg["datasets"]["irrigation"]

    zip_path = raw_cache_path("gmia_v5_aei_pct_asc.zip", exposure_cfg)
    download_file(ds_cfg["zip_url"], zip_path, overwrite=overwrite)

    extract_dir = zip_path.parent / "gmia_v5_aei_pct_asc"
    asc_path = extract_single_file(zip_path, extract_dir, ".asc")

    with rasterio.open(asc_path) as src:
        array = src.read(1).astype("float64")
        nodata = src.nodata
        transform = src.transform
        crs = src.crs or _ASSUMED_CRS

    if nodata is not None:
        array = np.where(array == nodata, np.nan, array)
    array = np.where(array < 0, np.nan, array)  # defensive: a % cannot be negative

    resampled = reproject_array_to_grid(
        array, transform, crs, resampling=Resampling.average, cfg=domain_cfg
    )

    dest = output_path("irrigation_gmia", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "assumed_crs": str(crs),
        },
        cfg=domain_cfg,
    )
    return dest
