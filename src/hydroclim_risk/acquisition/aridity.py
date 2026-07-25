"""Download CGIAR-CSI's Global Aridity Index (v3.1, annual) and resample it
onto the analysis grid.

Source verified 2026-07-24: direct, no-auth ZIP download from figshare
(ndownloader.figshare.com, DOI 10.6084/m9.figshare.7504448), global GeoTIFF,
30 arcsecond (~1km) resolution. The zip bundles both the Aridity Index
(ai_v31_yr.tif) and potential evapotranspiration (et0_v31_yr.tif) plus
sidecar files -- only the aridity index is extracted here.

Like GHS-BUILT, this is a huge global 30-arcsecond grid (comparable pixel
count to GHS-BUILT's ~924M) -- only the window covering Ethiopia's domain is
read, never the full raster.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from hydroclim_risk.acquisition.common import (
    download_file,
    extract_single_file,
    output_path,
    raw_cache_path,
    reproject_array_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml


def download_aridity(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, resample, and write the aridity-index vulnerability layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["aridity"]
    domain = domain_cfg["domain"]

    zip_path = raw_cache_path("cgiar_ai_et0_annual_v31.zip", exposure_cfg)
    download_file(ds_cfg["zip_url"], zip_path, overwrite=overwrite)

    extract_dir = zip_path.parent / "cgiar_ai_et0_annual_v31"
    tif_path = extract_single_file(zip_path, extract_dir, ".tif", name_contains="ai_v31")

    with rasterio.open(tif_path) as src:
        window = from_bounds(
            domain["lon_min"], domain["lat_min"], domain["lon_max"], domain["lat_max"],
            transform=src.transform,
        ).round_lengths().round_offsets()
        array = src.read(1, window=window).astype("float64")
        nodata = src.nodata
        transform = src.window_transform(window)
        crs = src.crs
        scale = src.scales[0] if src.scales and src.scales[0] not in (None, 1.0) else None

    if scale is None:
        # Verified empirically 2026-07-24: the real GeoTIFF has no embedded
        # GDAL scale tag (defaults to 1.0), but raw values run up to ~14700
        # -- physically impossible for an Aridity Index (expected range is
        # roughly 0-3). CGIAR-CSI's documented convention is to distribute
        # AI multiplied by 10000 as integers; applying that fallback gives a
        # sensible 0-1.5ish range instead.
        scale = 0.0001

    if nodata is not None:
        array = np.where(array == nodata, np.nan, array)
    array = array * scale

    resampled = reproject_array_to_grid(array, transform, crs, resampling=Resampling.average, cfg=domain_cfg)

    dest = output_path("aridity", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "scale_factor_applied": str(scale),
        },
        cfg=domain_cfg,
    )
    return dest
