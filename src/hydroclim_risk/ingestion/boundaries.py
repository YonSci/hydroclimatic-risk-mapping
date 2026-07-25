"""Load and validate the Ethiopia admin-boundary shapefiles (admin 0-3).

Field names confirmed by direct inspection on 2026-07-24 (standard COD-AB
naming): adm{level}_name / adm{level}_pcode at every level, EPSG:4326, no
invalid/empty/null geometries in the current files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
from pyproj import CRS

from hydroclim_risk.config import PROJECT_ROOT, load_data_config

SHAPEFILE_NAMES = {
    0: "eth_admin0.shp",
    1: "eth_admin1.shp",
    2: "eth_admin2.shp",
    3: "eth_admin3.shp",
}

NAME_FIELDS = {level: f"adm{level}_name" for level in SHAPEFILE_NAMES}
CODE_FIELDS = {level: f"adm{level}_pcode" for level in SHAPEFILE_NAMES}

# Reporting-level selection per references/project-context.md step 7:
# national maps use admin 0, regional summaries admin 1, zonal admin 2,
# woreda admin 3.
REPORTING_LEVELS = {
    "national": 0,
    "regional": 1,
    "zonal": 2,
    "woreda": 3,
}


class BoundaryValidationError(ValueError):
    """Raised when an admin-boundary shapefile fails schema/geometry checks."""


def _resolve_boundaries_dir(cfg: dict[str, Any] | None) -> Path:
    cfg = cfg or load_data_config()
    return PROJECT_ROOT / cfg["paths"]["boundaries_dir"]


def _validate_boundaries(gdf: gpd.GeoDataFrame, level: int, cfg: dict[str, Any]) -> None:
    expected_crs = CRS(cfg["domain"]["crs"])
    if gdf.crs is None or CRS(gdf.crs) != expected_crs:
        raise BoundaryValidationError(
            f"admin{level} CRS = {gdf.crs}, expected {expected_crs.to_string()}"
        )

    for field in (NAME_FIELDS[level], CODE_FIELDS[level]):
        if field not in gdf.columns:
            raise BoundaryValidationError(f"admin{level} is missing expected field '{field}'")

    null_geom = gdf.geometry.isna()
    empty_geom = gdf.geometry.is_empty
    invalid_geom = ~gdf.geometry.is_valid

    bad = null_geom | empty_geom | invalid_geom
    if bad.any():
        bad_codes = gdf.loc[bad, CODE_FIELDS[level]].tolist()
        raise BoundaryValidationError(
            f"admin{level} has {int(bad.sum())} invalid/empty/null geometries: {bad_codes}"
        )

    dupes = gdf[CODE_FIELDS[level]].duplicated()
    if dupes.any():
        raise BoundaryValidationError(
            f"admin{level} has {int(dupes.sum())} duplicate {CODE_FIELDS[level]} values"
        )


def load_admin_boundaries(
    level: int, validate: bool = True, cfg: dict[str, Any] | None = None
) -> gpd.GeoDataFrame:
    """Load one admin level's boundaries as a GeoDataFrame.

    `level` is 0 (national) through 3 (woreda) — see REPORTING_LEVELS for the
    name-to-level mapping used for report selection.
    """
    if level not in SHAPEFILE_NAMES:
        raise ValueError(f"level must be one of {sorted(SHAPEFILE_NAMES)}, got {level}")

    cfg = cfg or load_data_config()
    path = _resolve_boundaries_dir(cfg) / SHAPEFILE_NAMES[level]
    gdf = gpd.read_file(path)

    if validate:
        _validate_boundaries(gdf, level, cfg)

    return gdf
