"""Download FAO GLW4 (2020) livestock-density rasters and resample them onto
the analysis grid, conserving total head count.

Source verified 2026-07-24: direct, no-auth GeoTIFF download URLs on Google
Cloud Storage (storage.googleapis.com/fao-gismgr-glw4-2020-data/...), global
extent, 5 arcmin (~10km) resolution, units head/km^2 (already a density, so
resample_count_to_grid(is_density=True) is used).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from hydroclim_risk.acquisition.common import (
    download_file,
    output_path,
    raw_cache_path,
    resample_count_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_yaml


def download_livestock(species: str, exposure_cfg: dict[str, Any] | None = None, overwrite: bool = False) -> Path:
    """Download, resample, and write one species' livestock exposure layer.

    `species` must be a key in config/exposure_data.yaml's
    datasets.livestock.species (currently cattle, sheep, goats).
    """
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    ds_cfg = exposure_cfg["datasets"]["livestock"]
    if species not in ds_cfg["species"]:
        raise ValueError(f"species must be one of {sorted(ds_cfg['species'])}, got {species!r}")

    url = f"{ds_cfg['base_url']}/{ds_cfg['species'][species]}"
    raw_path = raw_cache_path(f"glw4_{species}.tif", exposure_cfg)
    download_file(url, raw_path, overwrite=overwrite)

    with rasterio.open(raw_path) as src:
        density = src.read(1).astype("float64")
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
        src_res_deg = abs(transform.a)

    if nodata is not None:
        density = np.where(density == nodata, np.nan, density)
    density = np.where(density < 0, np.nan, density)

    resampled = resample_count_to_grid(
        density, transform, crs, src_resolution_deg=src_res_deg, is_density=True,
    )

    dest = output_path(f"livestock_{species}", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=f"{species}_head_count",
        tags={
            "source": ds_cfg["source_name"],
            "species": species,
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "native_units": ds_cfg["native_units"],
        },
    )
    return dest
