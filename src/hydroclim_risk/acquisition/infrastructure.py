"""Download Geofabrik's Ethiopia OSM extract and derive two infrastructure
exposure layers: road length (km) and building count, both per
analysis-grid cell.

Source verified 2026-07-24: direct, no-auth shapefile ZIP download from
Geofabrik (download.geofabrik.de/africa/ethiopia-latest-free.shp.zip).
Standard Geofabrik "free" shapefile theme layout includes
gis_osm_roads_free_1.shp (lines) and gis_osm_buildings_a_free_1.shp
(polygons), among many other themes not used here.

Roads are vector LINES -- there's no meaningful "fraction of cell" the way
there is for cropland's area classes, so road exposure is computed as total
road length (km) intersecting each cell, via a real vector overlay (not
rasterization), with geodesic (WGS84 ellipsoid) length via pyproj so length
is correct regardless of a line segment's orientation or latitude. Buildings
are polygons; building COUNT per cell is computed via centroid-in-cell
binning (same point-in-cell pattern as poverty.py/healthsites.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from pyproj import Geod
from shapely.geometry import box

from hydroclim_risk.acquisition.common import (
    analysis_grid_transform_and_shape,
    download_file,
    extract_single_file,
    output_path,
    raw_cache_path,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml

_GEOD = Geod(ellps="WGS84")


def _grid_cell_polygons(domain_cfg: dict[str, Any]) -> gpd.GeoDataFrame:
    domain = domain_cfg["domain"]
    res = domain["resolution_deg"]
    _, height, width = analysis_grid_transform_and_shape(domain_cfg)

    rows, cols, geoms = [], [], []
    for r in range(height):
        lat_top = domain["lat_max"] - r * res
        lat_bottom = lat_top - res
        for c in range(width):
            lon_left = domain["lon_min"] + c * res
            rows.append(r)
            cols.append(c)
            geoms.append(box(lon_left, lat_bottom, lon_left + res, lat_top))
    return gpd.GeoDataFrame({"row": rows, "col": cols}, geometry=geoms, crs=domain["crs"])


def _extract_shp(zip_path: Path, name_contains: str) -> gpd.GeoDataFrame:
    extract_dir = zip_path.parent / "ethiopia-latest-free"
    shp_path = extract_single_file(zip_path, extract_dir, ".shp", name_contains=name_contains)
    return gpd.read_file(shp_path)


def download_roads(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, overlay, and write the road-length (km per cell) exposure layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["infrastructure"]

    zip_path = raw_cache_path("ethiopia-latest-free.shp.zip", exposure_cfg)
    download_file(ds_cfg["shp_zip_url"], zip_path, overwrite=overwrite)

    roads = _extract_shp(zip_path, "roads_free")
    roads = roads.to_crs(domain_cfg["domain"]["crs"]) if roads.crs else roads.set_crs(domain_cfg["domain"]["crs"])

    cells = _grid_cell_polygons(domain_cfg)
    overlay = gpd.overlay(roads[["geometry"]], cells, how="intersection", keep_geom_type=False)
    overlay = overlay[~overlay.geometry.is_empty]

    lengths_km = np.array([_GEOD.geometry_length(geom) / 1000.0 for geom in overlay.geometry])

    _, height, width = analysis_grid_transform_and_shape(domain_cfg)
    grid = np.zeros((height, width))
    np.add.at(grid, (overlay["row"].to_numpy(), overlay["col"].to_numpy()), lengths_km)

    dest = output_path("roads", exposure_cfg)
    write_grid_geotiff(
        grid,
        dest,
        variable=ds_cfg["road_variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": "geodesic_length_sum_per_cell",
        },
        cfg=domain_cfg,
    )
    return dest


def download_buildings(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, bin, and write the building-count exposure layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["infrastructure"]

    zip_path = raw_cache_path("ethiopia-latest-free.shp.zip", exposure_cfg)
    download_file(ds_cfg["shp_zip_url"], zip_path, overwrite=overwrite)

    buildings = _extract_shp(zip_path, "buildings_a_free")
    buildings = (
        buildings.to_crs(domain_cfg["domain"]["crs"]) if buildings.crs else buildings.set_crs(domain_cfg["domain"]["crs"])
    )
    # a handful of empty/null geometries (e.g. 3 of 2.5M in the real Ethiopia
    # extract) have no centroid -- drop them explicitly rather than letting
    # NaN silently flow into the int index cast below
    buildings = buildings[~(buildings.geometry.is_empty | buildings.geometry.isna())]
    centroids = buildings.geometry.centroid

    domain = domain_cfg["domain"]
    res = domain["resolution_deg"]
    _, height, width = analysis_grid_transform_and_shape(domain_cfg)

    col_idx = np.floor((centroids.x.to_numpy() - domain["lon_min"]) / res).astype(int)
    row_idx = np.floor((domain["lat_max"] - centroids.y.to_numpy()) / res).astype(int)
    in_bounds = (row_idx >= 0) & (row_idx < height) & (col_idx >= 0) & (col_idx < width)

    grid = np.zeros((height, width))
    np.add.at(grid, (row_idx[in_bounds], col_idx[in_bounds]), 1)

    dest = output_path("buildings", exposure_cfg)
    write_grid_geotiff(
        grid,
        dest,
        variable=ds_cfg["building_variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": "centroid_count_per_cell",
        },
        cfg=domain_cfg,
    )
    return dest
