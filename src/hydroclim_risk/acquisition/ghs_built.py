"""Download JRC's GHS-BUILT-S (built-up surface) raster and resample it onto
the analysis grid, conserving total built-up area.

Source verified 2026-07-24: direct, no-auth ZIP download from JRC's public
FTP (jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/...), WGS84 geographic
(4326) 30-arcsecond (~1km) global mosaic -- deliberately chosen over the
Mollweide-projected (54009) tiled variants, which use an equal-area tile
grid unrelated to lat/lon and would need extra reprojection complexity.
Units are m^2 of built-up surface per source pixel -- an extensive area
quantity, same conservation requirement as population count, so
resample_count_to_grid(is_density=False) is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import from_bounds

from hydroclim_risk.acquisition.common import (
    download_file,
    extract_single_file,
    output_path,
    raw_cache_path,
    resample_count_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml


def download_ghs_built(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, resample, and write the built-up-surface exposure layer.

    GHS-BUILT-S's global 30-arcsecond grid is ~924M pixels (21384x43201) --
    far too large to read into memory in full. Only the window covering
    Ethiopia's domain is read.
    """
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["ghs_built"]
    domain = domain_cfg["domain"]

    zip_path = raw_cache_path("ghs_built_s_e2020_4326_30ss.zip", exposure_cfg)
    download_file(ds_cfg["zip_url"], zip_path, overwrite=overwrite)

    extract_dir = zip_path.parent / "ghs_built_s_e2020_4326_30ss"
    tif_path = extract_single_file(zip_path, extract_dir, ".tif")

    with rasterio.open(tif_path) as src:
        window = from_bounds(
            domain["lon_min"], domain["lat_min"], domain["lon_max"], domain["lat_max"],
            transform=src.transform,
        ).round_lengths().round_offsets()
        area_m2 = src.read(1, window=window).astype("float64")
        nodata = src.nodata
        transform = src.window_transform(window)
        crs = src.crs
        src_res_deg = abs(src.transform.a)

    if nodata is not None:
        area_m2 = np.where(area_m2 == nodata, np.nan, area_m2)
    area_m2 = np.where(area_m2 < 0, np.nan, area_m2)

    resampled = resample_count_to_grid(
        area_m2, transform, crs, src_resolution_deg=src_res_deg, is_density=False, cfg=domain_cfg,
    )

    dest = output_path("ghs_built", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "native_units": ds_cfg["native_units"],
        },
        cfg=domain_cfg,
    )
    return dest
