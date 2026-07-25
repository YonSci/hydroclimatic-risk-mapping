"""Download ESA WorldCover 2021 v200 tiles covering Ethiopia's domain (via
efficient decimated remote reads, not full-tile downloads) and resample the
cropland class into a cropland-fraction exposure layer.

Source verified 2026-07-24: public, no-auth Cloud-Optimized GeoTIFFs on AWS
S3 (s3://esa-worldcover/v200/2021/map/), 3x3-degree tiles named by SW-corner
coordinate (e.g. ESA_WorldCover_10m_2021_v200_N03E033_Map.tif) -- confirmed
via a live bucket listing. Because 3 degrees is an exact multiple of the
analysis grid's 0.25 deg resolution, every tile boundary aligns exactly with
an analysis-grid cell boundary: no destination cell ever straddles two
tiles.

Tiles are NOT downloaded in full (a single tile can be 150+MB at native 10m,
and the domain needs ~20 tiles). Instead each tile is opened remotely via
GDAL's /vsicurl/ virtual filesystem and read at a decimated resolution
before classifying into a binary cropland mask.

IMPORTANT (found 2026-07-24 while building this): GDAL's warp "average"
resampling, used via rasterio.warp.reproject, does NOT do true exhaustive
block-averaging at large downsampling ratios -- verified empirically with a
20x20 alternating checkerboard mask collapsed to 1 pixel: it returned 1.0,
not the correct mean of 0.5. It's only reliable for smooth/slowly-varying
fields (which is why hazard/vulnerability rasters elsewhere in this project,
already smooth continuous fields, are unaffected), not sharp binary masks.
So cropland fraction is computed with an exact numpy block-mean instead
(reshape the decimated mask into (n_cells_per_tile, samples_per_cell,
n_cells_per_tile, samples_per_cell) and average over the sample axes) --
this is only valid because tile and analysis-grid boundaries are exactly
aligned (see above); it would not generalize to an arbitrary reprojection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError

from hydroclim_risk.acquisition.common import analysis_grid_transform_and_shape, output_path, write_grid_geotiff
from hydroclim_risk.config import load_data_config, load_yaml

_SAMPLES_PER_ANALYSIS_CELL = 20  # decimated-read fineness relative to the 0.25 deg grid


def _tiles_covering_bbox(
    lon_min: float, lon_max: float, lat_min: float, lat_max: float, tile_size_deg: int
) -> list[tuple[str, str]]:
    lon_start = int(np.floor(lon_min / tile_size_deg)) * tile_size_deg
    lon_end = int(np.ceil(lon_max / tile_size_deg)) * tile_size_deg
    lat_start = int(np.floor(lat_min / tile_size_deg)) * tile_size_deg
    lat_end = int(np.ceil(lat_max / tile_size_deg)) * tile_size_deg

    tiles = []
    for lat in range(lat_start, lat_end, tile_size_deg):
        lat_tag = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
        for lon in range(lon_start, lon_end, tile_size_deg):
            lon_tag = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            tiles.append((lat_tag, lon_tag))
    return tiles


def _parse_lat_tag(tag: str) -> int:
    return int(tag[1:]) if tag[0] == "N" else -int(tag[1:])


def _parse_lon_tag(tag: str) -> int:
    return int(tag[1:]) if tag[0] == "E" else -int(tag[1:])


def _tile_url(ds_cfg: dict[str, Any], lat_tag: str, lon_tag: str) -> str:
    filename = ds_cfg["tile_name_pattern"].format(lat_tag=lat_tag, lon_tag=lon_tag)
    return f"https://{ds_cfg['s3_bucket']}.s3.eu-central-1.amazonaws.com/{ds_cfg['s3_prefix']}/{filename}"


def _resample_one_tile(
    url: str,
    decimated_side: int,
    cropland_class_value: int,
    domain_cfg: dict[str, Any],
    lat_tag: str,
    lon_tag: str,
    tile_size_deg: int,
) -> np.ndarray | None:
    """Read one tile at a decimated resolution, classify, and place an exact
    block-mean cropland fraction into a full-analysis-grid array (NaN
    outside this tile's footprint). Returns None if the tile doesn't exist.
    """
    vsi_path = f"/vsicurl/{url}"
    try:
        with rasterio.open(vsi_path) as src:
            decimated = src.read(1, out_shape=(decimated_side, decimated_side), resampling=Resampling.nearest)
    except RasterioIOError:
        return None

    mask = (decimated == cropland_class_value).astype("float64")

    domain = domain_cfg["domain"]
    res = domain["resolution_deg"]
    n_cells_per_tile = int(round(tile_size_deg / res))
    samples_per_cell = decimated_side // n_cells_per_tile

    block = mask.reshape(n_cells_per_tile, samples_per_cell, n_cells_per_tile, samples_per_cell)
    tile_fraction = block.mean(axis=(1, 3))

    _, dst_height, dst_width = analysis_grid_transform_and_shape(domain_cfg)
    combined = np.full((dst_height, dst_width), np.nan, dtype="float64")

    lat_deg = _parse_lat_tag(lat_tag)
    lon_deg = _parse_lon_tag(lon_tag)
    row_start = int(round((domain["lat_max"] - (lat_deg + tile_size_deg)) / res))
    col_start = int(round((lon_deg - domain["lon_min"]) / res))
    row_end, col_end = row_start + n_cells_per_tile, col_start + n_cells_per_tile

    # clip to destination bounds (defensive -- exact for this domain, but
    # keeps this correct even if the domain isn't perfectly tile-aligned)
    src_row0, src_col0 = max(0, -row_start), max(0, -col_start)
    dst_row0, dst_col0 = max(0, row_start), max(0, col_start)
    dst_row1, dst_col1 = min(dst_height, row_end), min(dst_width, col_end)
    if dst_row0 >= dst_row1 or dst_col0 >= dst_col1:
        return None

    combined[dst_row0:dst_row1, dst_col0:dst_col1] = tile_fraction[
        src_row0 : src_row0 + (dst_row1 - dst_row0), src_col0 : src_col0 + (dst_col1 - dst_col0)
    ]
    return combined


def download_cropland(
    exposure_cfg: dict[str, Any] | None = None, domain_cfg: dict[str, Any] | None = None
) -> Path:
    """Build and write the cropland-fraction exposure layer (0-1 fraction of
    each analysis-grid cell classified as cropland by ESA WorldCover 2021).
    """
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["cropland"]
    domain = domain_cfg["domain"]

    tile_size = ds_cfg["tile_size_deg"]
    n_cells_per_tile = int(round(tile_size / domain["resolution_deg"]))
    decimated_side = n_cells_per_tile * _SAMPLES_PER_ANALYSIS_CELL

    tiles = _tiles_covering_bbox(
        domain["lon_min"], domain["lon_max"], domain["lat_min"], domain["lat_max"], tile_size
    )

    _, dst_height, dst_width = analysis_grid_transform_and_shape(domain_cfg)
    combined = np.full((dst_height, dst_width), np.nan, dtype="float64")
    n_used = 0

    for lat_tag, lon_tag in tiles:
        url = _tile_url(ds_cfg, lat_tag, lon_tag)
        tile_result = _resample_one_tile(
            url, decimated_side, ds_cfg["cropland_class_value"], domain_cfg, lat_tag, lon_tag, tile_size
        )
        if tile_result is None:
            continue
        n_used += 1
        fill = ~np.isnan(tile_result)
        combined[fill] = tile_result[fill]

    dest = output_path("cropland", exposure_cfg)
    write_grid_geotiff(
        combined,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": "exact_block_mean_of_binary_mask",
            "cropland_class_value": str(ds_cfg["cropland_class_value"]),
            "n_tiles_requested": str(len(tiles)),
            "n_tiles_found": str(n_used),
        },
        cfg=domain_cfg,
    )
    return dest
