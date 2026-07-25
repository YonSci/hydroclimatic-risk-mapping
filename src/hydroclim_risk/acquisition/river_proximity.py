"""Derive a river/water-body proximity wet-vulnerability sensitivity layer:
distance (km) from each analysis-grid cell's centroid to the nearest OSM
waterway (river/stream, line) or water body (lake/reservoir, polygon) --
land near rivers and lakes is more exposed to flooding and waterlogging.

No new download needed: Geofabrik's Ethiopia OSM extract
(ethiopia-latest-free.shp.zip, already cached by acquisition/infrastructure.py
for roads/buildings -- see config/exposure_data.yaml's `infrastructure`
entry for the source URL) also bundles gis_osm_waterways_free_1.shp (lines)
and gis_osm_water_a_free_1.shp (polygons), confirmed present via a zipfile
listing 2026-07-25.

Distance is computed in a local Azimuthal Equidistant projection centered on
Ethiopia (lat_0=9, lon_0=40) rather than a UTM zone, since Ethiopia's ~15
degree longitude span crosses multiple UTM zones -- AEQD preserves distance
accuracy radiating from its center reasonably well across Ethiopia's ~1200km
extent, in the same spirit as the spherical-Earth approximation already used
project-wide (acquisition.common.cell_area_km2). The OSM extract is clipped
to Ethiopia's territory, so a river just across the border may be missed for
a handful of border cells -- a known, minor edge-case limitation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from hydroclim_risk.acquisition.common import (
    analysis_grid_transform_and_shape,
    download_file,
    extract_single_file,
    output_path,
    raw_cache_path,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml

_AEQD_ETHIOPIA = "+proj=aeqd +lat_0=9 +lon_0=40 +datum=WGS84 +units=m +no_defs"


def _extract_shp(zip_path: Path, name_contains: str) -> gpd.GeoDataFrame:
    extract_dir = zip_path.parent / "ethiopia-latest-free"
    shp_path = extract_single_file(zip_path, extract_dir, ".shp", name_contains=name_contains)
    return gpd.read_file(shp_path)


def _grid_cell_centroids(domain_cfg: dict[str, Any]) -> gpd.GeoDataFrame:
    domain = domain_cfg["domain"]
    res = domain["resolution_deg"]
    _, height, width = analysis_grid_transform_and_shape(domain_cfg)

    rows, cols, geoms = [], [], []
    for r in range(height):
        lat_center = domain["lat_max"] - (r + 0.5) * res
        for c in range(width):
            lon_center = domain["lon_min"] + (c + 0.5) * res
            rows.append(r)
            cols.append(c)
            geoms.append(Point(lon_center, lat_center))
    return gpd.GeoDataFrame({"row": rows, "col": cols}, geometry=geoms, crs=domain["crs"])


def download_river_proximity(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download (if needed), compute, and write the river/water-body
    distance sensitivity layer.
    """
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["river_proximity"]

    zip_path = raw_cache_path("ethiopia-latest-free.shp.zip", exposure_cfg)
    download_file(ds_cfg["shp_zip_url"], zip_path, overwrite=overwrite)

    waterways = _extract_shp(zip_path, "waterways_free")
    water_bodies = _extract_shp(zip_path, "water_a_free")

    water_features = pd.concat(
        [waterways[["geometry"]], water_bodies[["geometry"]]], ignore_index=True
    )
    water_features = gpd.GeoDataFrame(water_features, crs=waterways.crs or domain_cfg["domain"]["crs"])
    water_features = water_features[~(water_features.geometry.is_empty | water_features.geometry.isna())]

    cells = _grid_cell_centroids(domain_cfg)

    water_aeqd = water_features.to_crs(_AEQD_ETHIOPIA)
    cells_aeqd = cells.to_crs(_AEQD_ETHIOPIA)

    joined = gpd.sjoin_nearest(cells_aeqd, water_aeqd[["geometry"]], distance_col="dist_m")
    # sjoin_nearest can return duplicate rows on exact-distance ties; keep one per cell
    joined = joined.groupby(["row", "col"], as_index=False)["dist_m"].min()

    _, height, width = analysis_grid_transform_and_shape(domain_cfg)
    grid = np.full((height, width), np.nan)
    grid[joined["row"].to_numpy(), joined["col"].to_numpy()] = joined["dist_m"].to_numpy() / 1000.0

    dest = output_path("river_distance", exposure_cfg)
    write_grid_geotiff(
        grid,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": "nearest_feature_distance_aeqd_km",
        },
        cfg=domain_cfg,
    )
    return dest
