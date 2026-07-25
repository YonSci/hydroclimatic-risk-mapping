import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import LineString, Point, Polygon

from hydroclim_risk.acquisition.river_proximity import download_river_proximity
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


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


def _write_synthetic_water_zip(zip_path: Path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = zip_path.parent / "_build"

    # a north-south river running straight through the middle of the domain
    river = LineString([(40.125, DOMAIN["lat_min"]), (40.125, DOMAIN["lat_max"])])
    waterways_gdf = gpd.GeoDataFrame({"geometry": [river, Polygon()]}, crs="EPSG:4326")  # + 1 empty, like real extracts

    lake = Point(45.0, 5.0).buffer(0.05)
    water_a_gdf = gpd.GeoDataFrame({"geometry": [lake]}, crs="EPSG:4326")

    with zipfile.ZipFile(zip_path, "w") as zf:
        _zip_shapefile(waterways_gdf, tmp_dir, "gis_osm_waterways_free_1", zf)
        _zip_shapefile(water_a_gdf, tmp_dir, "gis_osm_water_a_free_1", zf)


def test_download_river_proximity_distance_increases_away_from_river(tmp_path: Path, monkeypatch):
    cfg = _cfg_with_tmp_dirs(tmp_path)

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_water_zip(Path(dest_path))
        return Path(dest_path)

    monkeypatch.setattr("hydroclim_risk.acquisition.river_proximity.download_file", fake_download_file)

    dest = download_river_proximity(exposure_cfg=cfg)

    with rasterio.open(dest) as src:
        grid = src.read(1)
        tags = src.tags()

    assert tags["variable"] == "river_water_body_distance_km"
    assert tags["source"] == "geofabrik_osm"
    assert np.isfinite(grid).all()  # nearest-feature distance always resolves, no gaps expected

    res = DOMAIN["resolution_deg"]
    river_col = int((40.125 - DOMAIN["lon_min"]) / res)
    far_col = 0  # westernmost column, ~7 degrees from the river

    row = grid.shape[0] // 2
    assert grid[row, river_col] < grid[row, far_col]
    assert grid[row, river_col] < 20.0  # within one cell width of the river, should be small
    assert grid[row, far_col] > 500.0  # ~7 degrees (~700km) away

    # distance must increase monotonically moving away from the river column, both directions
    row_values = grid[row, : river_col + 1]
    assert np.all(np.diff(row_values) <= 1e-6)
