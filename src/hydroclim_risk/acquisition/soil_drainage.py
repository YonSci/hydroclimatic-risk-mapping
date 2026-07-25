"""Download ISRIC SoilGrids topsoil clay content and resample it onto the
analysis grid, as a soil-drainage proxy for wet-vulnerability sensitivity --
high clay content impedes infiltration and drainage, so land is more prone
to waterlogging after heavy rain.

Source verified 2026-07-25: SoilGrids' REST API (rest.soilgrids.org) is
documented as currently paused/rate-limited (5 calls/min) and unsuitable for
a bulk grid. Instead, ISRIC's public WebDAV static file server
(files.isric.org/soilgrids/latest/data/clay/) serves the same data as
Cloud-Optimized GeoTIFFs behind a GDAL VRT, with anonymous read access and
no API key -- confirmed via a live directory listing and a successful
/vsicurl/ windowed read.

The source CRS is Interrupted Goode Homolosine (an equal-area projection),
NOT plain lat/lon -- confirmed via rasterio.open(...).crs on the live VRT.
A rasterio WarpedVRT is used to reproject on the fly during the (decimated,
windowed) read, avoiding a manual Homolosine bounding-box computation.

No embedded GDAL scale factor is present on the source band (scales=(1.0,)),
but ISRIC's documented convention is that clay content is delivered as
g/kg x 10 (i.e. divide by 10 for percent). Empirically verified 2026-07-25:
applying this 0.1 factor to the band's own global STATISTICS_MEAN tag (244.5)
gives ~24.5% average clay content, matching known global topsoil averages --
confirming the conversion factor is correct, following the same
empirical-validation approach used for CGIAR aridity's scale factor
(acquisition/aridity.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.windows import bounds as window_bounds
from rasterio.windows import from_bounds

from hydroclim_risk.acquisition.common import output_path, reproject_array_to_grid, write_grid_geotiff
from hydroclim_risk.config import load_data_config, load_yaml

_CLAY_SCALE_FACTOR = 0.1  # g/kg x10 -> percent, verified against band STATISTICS_MEAN (2026-07-25)
_OVERSAMPLE_FACTOR = 5  # intermediate decimated read resolution, as a multiple of the final grid


def download_soil_drainage(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
) -> Path:
    """Download, reproject, and write the soil-clay-content sensitivity layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["soil_drainage"]
    domain = domain_cfg["domain"]

    height, width = domain_cfg["domain"]["grid_shape"]
    out_shape = (height * _OVERSAMPLE_FACTOR, width * _OVERSAMPLE_FACTOR)

    with rasterio.open(ds_cfg["vrt_url"]) as src:
        with WarpedVRT(src, crs="EPSG:4326", resampling=Resampling.average) as vrt:
            window = from_bounds(
                domain["lon_min"], domain["lat_min"], domain["lon_max"], domain["lat_max"],
                transform=vrt.transform,
            ).round_lengths().round_offsets()
            array = vrt.read(1, window=window, out_shape=out_shape, resampling=Resampling.average).astype("float64")
            # window_transform() gives the NATIVE-resolution transform for
            # `window` -- wrong for this decimated (out_shape) read, which
            # has coarser pixels. Found 2026-07-25: using it directly made
            # the array's implied bounds a tiny sliver of the true window
            # (240x300 decimated pixels at NATIVE ~250m spacing covers only
            # ~0.6 deg, not the ~15x12 deg actually read), so the subsequent
            # reproject to the analysis grid only overlapped 5 cells.
            left, bottom, right, top = window_bounds(window, vrt.transform)
            transform = transform_from_bounds(left, bottom, right, top, out_shape[1], out_shape[0])
            nodata = vrt.nodata

    if nodata is not None:
        array = np.where(array == nodata, np.nan, array)
    array = array * _CLAY_SCALE_FACTOR

    # src_nodata must be passed explicitly: unlike ETOPO (gapless bedrock
    # coverage everywhere, land and sea), SoilGrids has real NaN gaps over
    # water within the domain rectangle (e.g. the Red Sea corner) -- found
    # 2026-07-25 when omitting src_nodata silently propagated NaN into
    # nearly every output cell (GDAL's average resampling has no way to
    # know NaN means "exclude" without this).
    resampled = reproject_array_to_grid(
        array, transform, "EPSG:4326", resampling=Resampling.average, src_nodata=np.nan, cfg=domain_cfg
    )

    dest = output_path("soil_clay", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "scale_factor_applied": str(_CLAY_SCALE_FACTOR),
        },
        cfg=domain_cfg,
    )
    return dest
