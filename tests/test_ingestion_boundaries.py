import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from hydroclim_risk.config import load_data_config
from hydroclim_risk.ingestion.boundaries import (
    CODE_FIELDS,
    NAME_FIELDS,
    REPORTING_LEVELS,
    BoundaryValidationError,
    _validate_boundaries,
    load_admin_boundaries,
)

CFG = load_data_config()


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_load_real_admin_boundaries(level: int):
    gdf = load_admin_boundaries(level)
    assert NAME_FIELDS[level] in gdf.columns
    assert CODE_FIELDS[level] in gdf.columns
    assert len(gdf) > 0
    assert gdf.geometry.is_valid.all()


def test_reporting_levels_map_to_admin_levels():
    assert REPORTING_LEVELS == {"national": 0, "regional": 1, "zonal": 2, "woreda": 3}
    for level in REPORTING_LEVELS.values():
        assert level in NAME_FIELDS


def test_validate_boundaries_rejects_missing_name_field():
    gdf = gpd.GeoDataFrame(
        {"adm0_pcode": ["ET"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs=CFG["domain"]["crs"],
    )
    with pytest.raises(BoundaryValidationError, match="adm0_name"):
        _validate_boundaries(gdf, level=0, cfg=CFG)


def test_validate_boundaries_rejects_invalid_geometry():
    # bowtie/self-intersecting polygon is a classic invalid geometry
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame(
        {"adm0_name": ["Test"], "adm0_pcode": ["T1"]},
        geometry=[bowtie],
        crs=CFG["domain"]["crs"],
    )
    with pytest.raises(BoundaryValidationError, match="invalid"):
        _validate_boundaries(gdf, level=0, cfg=CFG)


def test_validate_boundaries_rejects_wrong_crs():
    gdf = gpd.GeoDataFrame(
        {"adm0_name": ["Test"], "adm0_pcode": ["T1"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:3857",
    )
    with pytest.raises(BoundaryValidationError, match="CRS"):
        _validate_boundaries(gdf, level=0, cfg=CFG)


def test_validate_boundaries_rejects_duplicate_codes():
    gdf = gpd.GeoDataFrame(
        {"adm1_name": ["A", "B"], "adm1_pcode": ["X1", "X1"]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
        ],
        crs=CFG["domain"]["crs"],
    )
    with pytest.raises(BoundaryValidationError, match="duplicate"):
        _validate_boundaries(gdf, level=1, cfg=CFG)
