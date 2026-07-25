"""Download NOAA's ETOPO 2022 global relief model and derive two
terrain-based wet-vulnerability sensitivity layers: elevation (for
low-lying-area flood/waterlogging exposure) and slope (a flatness proxy --
flat terrain drains poorly and pools water, unlike steep terrain).

Source verified 2026-07-25: a single global 30-arcsecond (~900m) GeoTIFF,
no auth required, HTTP Range-request support confirmed (Accept-Ranges:
bytes), so this is read via GDAL's /vsicurl/ virtual filesystem as a
windowed read -- never the full 1.6GB global file. CRS is EPSG:9518 (WGS84 +
EGM2008 height, a compound CRS) but the horizontal grid is plain WGS84
lon/lat, so EPSG:4326 is used for reprojection purposes. Point-sampled
sanity check against known Ethiopian elevations (Addis Ababa ~2412m vs
real ~2355m; Danakil Depression ~-100m vs real ~-125m) confirmed correct
alignment.

No flow-accumulation library (richdem/pysheds/whitebox) is available or
verified in this environment, so a full Topographic Wetness Index is not
computed. Elevation + slope is a standard, documented simplification of TWI
when flow-accumulation tooling isn't available -- an explicit, defensible
approximation, not a full TWI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from hydroclim_risk.acquisition.common import output_path, reproject_array_to_grid, write_grid_geotiff
from hydroclim_risk.config import load_data_config, load_yaml

_ETOPO_URL = (
    "/vsicurl/https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/"
    "30s/30s_bed_elev_gtif/ETOPO_2022_v1_30s_N90W180_bed.tif"
)
_KM_PER_DEGREE_LAT_M = 111320.0  # meters, same spherical approximation as acquisition.common.cell_area_km2


def _read_etopo_window(domain: dict[str, Any]) -> tuple[np.ndarray, "rasterio.Affine", Any]:
    with rasterio.open(_ETOPO_URL) as src:
        window = from_bounds(
            domain["lon_min"], domain["lat_min"], domain["lon_max"], domain["lat_max"],
            transform=src.transform,
        ).round_lengths().round_offsets()
        array = src.read(1, window=window).astype("float64")
        nodata = src.nodata
        transform = src.window_transform(window)
    if nodata is not None:
        array = np.where(array == nodata, np.nan, array)
    return array, transform, "EPSG:4326"


def _slope_degrees(elevation: np.ndarray, transform: "rasterio.Affine") -> np.ndarray:
    """Slope (degrees) via a central-difference gradient at native
    resolution, using per-latitude meter spacing (lon spacing narrows by
    cos(lat); lat spacing is ~constant) -- same spherical-Earth convention
    used throughout this project (see acquisition.common.cell_area_km2).
    """
    res_deg = transform.a
    n_rows = elevation.shape[0]
    row_centers = np.arange(n_rows) + 0.5
    lats = transform.f + transform.e * row_centers  # transform.e is negative (north-up)

    dy_m = res_deg * _KM_PER_DEGREE_LAT_M
    dx_m = (res_deg * _KM_PER_DEGREE_LAT_M) * np.cos(np.radians(lats))[:, None]

    gy = np.gradient(elevation, axis=0) / dy_m
    gx = np.gradient(elevation, axis=1) / dx_m

    slope_rad = np.arctan(np.sqrt(gx**2 + gy**2))
    return np.degrees(slope_rad)


def download_terrain(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    """Derive and write the elevation and slope wet-sensitivity layers."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["terrain"]
    domain = domain_cfg["domain"]

    elevation, transform, crs = _read_etopo_window(domain)
    slope = _slope_degrees(elevation, transform)
    # propagate nodata gaps from elevation into the derived slope array
    slope = np.where(np.isfinite(elevation), slope, np.nan)

    elevation_grid = reproject_array_to_grid(elevation, transform, crs, resampling=Resampling.average, cfg=domain_cfg)
    slope_grid = reproject_array_to_grid(slope, transform, crs, resampling=Resampling.average, cfg=domain_cfg)

    tags = {
        "source": ds_cfg["source_name"],
        "license": ds_cfg["license"],
        "citation": ds_cfg["citation"],
    }

    elevation_dest = output_path("elevation", exposure_cfg)
    write_grid_geotiff(elevation_grid, elevation_dest, variable="elevation_m", tags=tags, cfg=domain_cfg)

    slope_dest = output_path("slope", exposure_cfg)
    write_grid_geotiff(
        slope_grid, slope_dest, variable="slope_degrees",
        tags={**tags, "aggregation": "native_30arcsec_gradient_then_mean"}, cfg=domain_cfg,
    )
    return elevation_dest, slope_dest
