from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from hydroclim_risk.config import load_data_config, load_thresholds_config
from hydroclim_risk.ingestion.geotiff import (
    BLOCKED_PRODUCTS,
    GeoTiffLoadError,
    build_filename,
    catalog,
    load_indicator,
    parse_filename,
)

REAL_CFG = load_data_config()
DOMAIN = REAL_CFG["domain"]


def _write_tif(path: Path, value: float, shape=(4, 5)):
    transform = from_origin(DOMAIN["lon_min"], DOMAIN["lat_max"], DOMAIN["resolution_deg"], DOMAIN["resolution_deg"])
    data = np.full(shape, value, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=shape[0], width=shape[1], count=1,
        dtype="float32", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(data, 1)


def _cfg_with_geotiff_dir(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_CFG.items()}
    cfg["paths"] = {**REAL_CFG["paths"], "geotiff_dir": str(tmp_path)}
    return cfg


@pytest.mark.parametrize(
    "filename,expected",
    [
        (
            "ethiopia_June_2026-05-01_rainfall_total_climatology_mean.tif",
            {"period": "June", "init_date": "2026-05-01", "indicator": "rainfall_total", "product_type": "climatology_mean"},
        ),
        (
            "ethiopia_JJAS_2026-05-01_spi_prob_drought.tif",
            {"period": "JJAS", "init_date": "2026-05-01", "indicator": "spi", "product_type": "prob_drought"},
        ),
        (
            "ethiopia_August_2026-05-01_percent_anomaly.tif",
            {"period": "August", "init_date": "2026-05-01", "indicator": "rainfall_total", "product_type": "percent_anomaly"},
        ),
        (
            "ethiopia_June_2026-05-01_percentile_median.tif",
            {"period": "June", "init_date": "2026-05-01", "indicator": "percentile", "product_type": "median"},
        ),
        (
            "ethiopia_June_2026-05-01_rx5day_mean.tif",
            {"period": "June", "init_date": "2026-05-01", "indicator": "rx5day", "product_type": "mean"},
        ),
        (
            "ethiopia_June_2026-05-01_cdd_percentile.tif",
            {"period": "June", "init_date": "2026-05-01", "indicator": "cdd", "product_type": "percentile"},
        ),
        (
            "ethiopia_JJAS_2026-05-01_rx5day_percentile.tif",
            {"period": "JJAS", "init_date": "2026-05-01", "indicator": "rx5day", "product_type": "percentile"},
        ),
    ],
)
def test_parse_filename(filename: str, expected: dict):
    assert parse_filename(filename) == expected


def test_parse_filename_rejects_garbage():
    with pytest.raises(GeoTiffLoadError):
        parse_filename("not_a_matching_name.tif")


def test_build_filename_roundtrips_parse():
    for filename in [
        "ethiopia_June_2026-05-01_cdd_mean.tif",
        "ethiopia_JJAS_2026-05-01_spi_prob_wet.tif",
        "ethiopia_August_2026-05-01_percent_anomaly.tif",
    ]:
        parsed = parse_filename(filename)
        rebuilt = build_filename(
            parsed["period"], parsed["indicator"], parsed["product_type"], parsed["init_date"]
        )
        assert rebuilt == filename


def test_load_indicator_blocks_known_broken_percentile_product(tmp_path: Path):
    cfg = _cfg_with_geotiff_dir(tmp_path)
    with pytest.raises(GeoTiffLoadError, match="known-broken"):
        load_indicator("June", "percentile", "climatology_mean", cfg=cfg)
    assert ("percentile", "climatology_mean") in BLOCKED_PRODUCTS


def test_load_indicator_blocks_known_broken_spi_climatology_product(tmp_path: Path):
    # Discovered 2026-07-24: a second instance of the same bug — see
    # outputs/geotiff/_deprecated_mislabeled/README.md.
    cfg = _cfg_with_geotiff_dir(tmp_path)
    with pytest.raises(GeoTiffLoadError, match="known-broken"):
        load_indicator("June", "spi", "climatology_mean", cfg=cfg)
    assert ("spi", "climatology_mean") in BLOCKED_PRODUCTS


def test_load_indicator_missing_file_raises(tmp_path: Path):
    cfg = _cfg_with_geotiff_dir(tmp_path)
    with pytest.raises(GeoTiffLoadError, match="No such"):
        load_indicator("June", "rainfall_total", "mean", cfg=cfg)


def test_load_indicator_reads_values(tmp_path: Path):
    filename = build_filename("June", "cdd", "mean", "2026-05-01")
    _write_tif(tmp_path / filename, value=12.0)
    cfg = _cfg_with_geotiff_dir(tmp_path)

    da = load_indicator("June", "cdd", "mean", cfg=cfg)
    assert float(da.values.max()) == pytest.approx(12.0)
    assert da.attrs["indicator"] == "cdd"
    assert da.attrs["product_type"] == "mean"


def test_load_indicator_caps_spi_extremes(tmp_path: Path):
    filename = build_filename("September", "spi", "median", "2026-05-01")
    path = tmp_path / filename
    transform = from_origin(DOMAIN["lon_min"], DOMAIN["lat_max"], DOMAIN["resolution_deg"], DOMAIN["resolution_deg"])
    data = np.array([[4.75, -4.75], [1.0, -1.0]], dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=2, width=2, count=1,
        dtype="float32", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(data, 1)

    cfg = _cfg_with_geotiff_dir(tmp_path)
    thresholds = load_thresholds_config()
    cap = thresholds["spi"]["cap_abs_value"]

    capped = load_indicator("September", "spi", "median", cfg=cfg)
    assert float(capped.values.max()) == pytest.approx(cap)
    assert float(capped.values.min()) == pytest.approx(-cap)

    uncapped = load_indicator("September", "spi", "median", apply_spi_cap=False, cfg=cfg)
    assert float(uncapped.values.max()) == pytest.approx(4.75)


def test_catalog_lists_synthetic_files(tmp_path: Path):
    _write_tif(tmp_path / build_filename("June", "cdd", "mean", "2026-05-01"), value=1.0)
    _write_tif(tmp_path / build_filename("June", "cwd", "anomaly", "2026-05-01"), value=1.0)
    (tmp_path / "README.md").write_text("not a tif")  # should be skipped, not raise

    cfg = _cfg_with_geotiff_dir(tmp_path)
    df = catalog(cfg=cfg)

    assert len(df) == 2
    assert set(df["indicator"]) == {"cdd", "cwd"}


def test_real_catalog_excludes_quarantined_percentile_climatology_mean():
    df = catalog()
    blocked = df[(df["indicator"] == "percentile") & (df["product_type"] == "climatology_mean")]
    assert blocked.empty


def test_real_catalog_excludes_quarantined_spi_climatology_mean():
    df = catalog()
    blocked = df[(df["indicator"] == "spi") & (df["product_type"] == "climatology_mean")]
    assert blocked.empty


@pytest.mark.parametrize("indicator", ["cdd", "cwd", "rx1day", "rx5day"])
def test_real_catalog_has_percentile_for_all_periods(indicator: str):
    df = catalog()
    rows = df[(df["indicator"] == indicator) & (df["product_type"] == "percentile")]
    assert set(rows["period"]) == {"June", "July", "August", "September", "JJAS"}


@pytest.mark.parametrize(
    "indicator", ["cdd", "cwd", "rx1day", "rx5day", "percentile"]
)
def test_real_percentile_products_are_in_0_100_range(indicator: str):
    product_type = "median" if indicator == "percentile" else "percentile"
    for period in ["June", "July", "August", "September", "JJAS"]:
        da = load_indicator(period, indicator, product_type)
        values = da.values[~np.isnan(da.values)]
        assert values.min() >= -0.01
        assert values.max() <= 100.01
