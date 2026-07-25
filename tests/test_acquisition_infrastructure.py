import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from pyproj import Geod
from shapely.geometry import LineString, Point, Polygon

from hydroclim_risk.acquisition.infrastructure import download_buildings, download_roads
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")
GEOD = Geod(ellps="WGS84")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _zip_shapefile(gdf: gpd.GeoDataFrame, base_dir: Path, name: str, zf: zipfile.ZipFile):
    shp_dir = base_dir / name
    shp_dir.mkdir(parents=True, exist_ok=True)
    shp_path = shp_dir / f"{name}.shp"
    gdf.to_file(shp_path, driver="ESRI Shapefile")
    for sibling in shp_dir.glob(f"{name}.*"):
        zf.write(sibling, arcname=sibling.name)


def _write_synthetic_osm_zip(zip_path: Path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = zip_path.parent / "_build"

    # a road entirely within cell (row=44, col=0) -- lon 33.0-33.25, lat 3.0-3.25
    # (bottom-left corner of the domain: row = (15-3)/0.25 - 1 = 47? let's use
    # a short segment safely inside a single cell near lon 33.05-33.10, lat 3.05)
    road_within = LineString([(33.05, 3.05), (33.10, 3.05)])
    # a road crossing the boundary between two adjacent columns at lon=33.25
    road_crossing = LineString([(33.20, 4.05), (33.30, 4.05)])
    roads_gdf = gpd.GeoDataFrame({"geometry": [road_within, road_crossing]}, crs="EPSG:4326")

    building_pts = [Point(33.05, 3.05), Point(33.06, 3.06), Point(33.06, 3.07), Point(40.0, 10.0)]
    geoms = [p.buffer(0.0001) for p in building_pts] + [Polygon()]  # + 1 empty geometry, like 3 real ones
    buildings_gdf = gpd.GeoDataFrame({"geometry": geoms}, crs="EPSG:4326")

    with zipfile.ZipFile(zip_path, "w") as zf:
        _zip_shapefile(roads_gdf, tmp_dir, "gis_osm_roads_free_1", zf)
        _zip_shapefile(buildings_gdf, tmp_dir, "gis_osm_buildings_a_free_1", zf)


def test_download_roads_sums_length_and_splits_at_cell_boundary(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_osm_zip(Path(dest_path))
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.infrastructure.download_file", fake_download_file)

    dest = download_roads(exposure_cfg=cfg)

    import rasterio

    with rasterio.open(dest) as src:
        grid = src.read(1)
        tags = src.tags()

    assert tags["source"] == "geofabrik_osm"
    assert tags["variable"] == "road_length_km"

    # road entirely inside one cell: total grid length should equal the
    # independently-computed geodesic length of both input roads combined
    expected_total_km = (
        GEOD.geometry_length(LineString([(33.05, 3.05), (33.10, 3.05)])) / 1000.0
        + GEOD.geometry_length(LineString([(33.20, 4.05), (33.30, 4.05)])) / 1000.0
    )
    assert grid.sum() == pytest.approx(expected_total_km, rel=1e-3)

    # the crossing road (lon 33.20-33.30 at lat 4.05, cell boundary at 33.25)
    # must appear split across (at least) two distinct nonzero cells
    nonzero_cells = np.count_nonzero(grid)
    assert nonzero_cells >= 2


def test_download_buildings_counts_by_centroid_and_drops_out_of_bounds(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_osm_zip(Path(dest_path))
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.infrastructure.download_file", fake_download_file)

    # an empty geometry must not trigger the "invalid value encountered in
    # cast" RuntimeWarning found in the real 2.5M-building Ethiopia extract
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        dest = download_buildings(exposure_cfg=cfg)

    import rasterio

    with rasterio.open(dest) as src:
        grid = src.read(1)
        tags = src.tags()

    assert tags["variable"] == "building_count"
    # all 4 real buildings are inside the domain (33-48E, 3-15N) and should
    # count; the 5th synthetic feature is an empty geometry (mirrors 3 real
    # ones found in the actual Ethiopia extract) and must be silently
    # dropped, not counted and not raising/warning
    assert grid.sum() == 4
