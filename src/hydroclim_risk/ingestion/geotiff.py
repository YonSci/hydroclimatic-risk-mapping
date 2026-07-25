"""Load indicator GeoTIFF products from outputs/geotiff/.

These files are produced by a separate sibling pipeline
(D:\\extremes-climate-indices, "Extremes Forecasting Tool - Ethiopia") — see
references/project-context.md and the project_sibling_pipeline memory.
hydroclim_risk does not recompute rainfall total/SPI/CDD/CWD/Rx1day/Rx5day
from raw `pr`; it consumes these products, with two consumption-time fixes:

1. A hard block on `percentile_climatology_mean` — confirmed mislabeled
   (contains rainfall_total mm values under a "percentile" name; its own
   embedded tags are self-contradictory). Already quarantined to
   outputs/geotiff/_deprecated_mislabeled/, blocked here defensively too.
2. SPI extreme capping — QC on 2026-07-24 found spi_mean/spi_median cells
   beyond +/-4 (max observed |4.75|). Applied by default per
   config/thresholds.yaml's spi.cap_abs_value (WMO extreme-category bound).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import rioxarray  # noqa: F401  (registers the .rio xarray accessor)
import xarray as xr

from hydroclim_risk.config import PROJECT_ROOT, load_data_config, load_thresholds_config

_FILENAME_RE = re.compile(r"^ethiopia_(?P<period>[A-Za-z]+)_(?P<init_date>[\d-]+)_(?P<rest>.+)\.tif$")

# Checked in order — longer/more-specific suffixes must come before the
# shorter suffixes they contain (e.g. "climatology_mean" before "mean",
# "prob_drought"/"prob_wet" before nothing overlapping, etc.).
_PRODUCT_SUFFIXES = [
    "climatology_mean",
    "prob_drought",
    "prob_wet",
    "percent_anomaly",
    "anomaly",
    "percentile",
    "mean",
    "median",
]

# percent_anomaly.tif carries no leading indicator token in the filename —
# it's the rainfall percentage-anomaly product (confirmed via embedded tags:
# units="%", units_converted_from="mm/day"). Special-cased below.
_BARE_FILENAME_INDICATORS = {"percent_anomaly": ("rainfall_total", "percent_anomaly")}

# Known-broken products (see data_percentile_mislabel_bug memory) — refuse to
# load even if they reappear outside the quarantine folder. Both are
# byte-for-byte duplicates of rainfall_total_climatology_mean.tif mislabeled
# under a different indicator name; confirmed 2026-07-24 this bug is confined
# to spi/percentile's "climatology_mean" export path specifically — cdd, cwd,
# rx1day, and rx5day's climatology_mean products are genuine (verified not
# byte-identical to rainfall_total_climatology_mean).
BLOCKED_PRODUCTS = {
    ("percentile", "climatology_mean"),
    ("spi", "climatology_mean"),
}


class GeoTiffLoadError(ValueError):
    """Raised for missing files, unparseable names, or blocked/known-bad products."""


def _geotiff_dir(cfg: dict[str, Any] | None) -> Path:
    cfg = cfg or load_data_config()
    return PROJECT_ROOT / cfg["paths"]["geotiff_dir"]


def parse_filename(filename: str) -> dict[str, str]:
    """Parse `ethiopia_{period}_{init_date}_{indicator}_{product_type}.tif`."""
    m = _FILENAME_RE.match(filename)
    if not m:
        raise GeoTiffLoadError(f"Filename does not match expected pattern: {filename}")
    period, init_date, rest = m.group("period"), m.group("init_date"), m.group("rest")

    if rest in _BARE_FILENAME_INDICATORS:
        indicator, product_type = _BARE_FILENAME_INDICATORS[rest]
        return {"period": period, "init_date": init_date, "indicator": indicator, "product_type": product_type}

    for suffix in _PRODUCT_SUFFIXES:
        if rest.endswith("_" + suffix):
            indicator = rest[: -(len(suffix) + 1)]
            return {"period": period, "init_date": init_date, "indicator": indicator, "product_type": suffix}

    raise GeoTiffLoadError(f"Could not identify a product-type suffix in: {filename}")


def build_filename(period: str, indicator: str, product_type: str, init_date: str) -> str:
    if (indicator, product_type) == ("rainfall_total", "percent_anomaly"):
        return f"ethiopia_{period}_{init_date}_percent_anomaly.tif"
    return f"ethiopia_{period}_{init_date}_{indicator}_{product_type}.tif"


def catalog(cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    """Tidy DataFrame of every available indicator GeoTIFF: period, indicator,
    product_type, init_date, path. Skips files that fail to parse (e.g. a
    stray README) and anything under _deprecated_mislabeled/ (glob is
    non-recursive, so the quarantine subfolder is naturally excluded).
    """
    cfg = cfg or load_data_config()
    rows = []
    for path in sorted(_geotiff_dir(cfg).glob("*.tif")):
        try:
            parsed = parse_filename(path.name)
        except GeoTiffLoadError:
            continue
        rows.append({**parsed, "path": str(path)})
    return pd.DataFrame(rows, columns=["period", "indicator", "product_type", "init_date", "path"])


def _cap_spi(da: xr.DataArray, cap: float) -> xr.DataArray:
    capped = da.clip(min=-cap, max=cap)
    capped.attrs = {**da.attrs, "spi_cap_applied": cap}
    return capped


def load_indicator(
    period: str,
    indicator: str,
    product_type: str,
    init_date: str = "2026-05-01",
    apply_spi_cap: bool = True,
    cfg: dict[str, Any] | None = None,
    thresholds_cfg: dict[str, Any] | None = None,
) -> xr.DataArray:
    """Load one indicator GeoTIFF as a georeferenced xarray DataArray.

    Raises GeoTiffLoadError for the known-broken (indicator="percentile",
    product_type="climatology_mean") combination — use
    (indicator="percentile", product_type="median") for a real percentile
    product instead.
    """
    if (indicator, product_type) in BLOCKED_PRODUCTS:
        raise GeoTiffLoadError(
            f"{indicator}_{product_type} is a known-broken product (mislabeled — contains "
            f"rainfall_total mm values, not a 0-100 percentile). See "
            f"outputs/geotiff/_deprecated_mislabeled/README.md. Refusing to load it."
        )

    cfg = cfg or load_data_config()
    filename = build_filename(period, indicator, product_type, init_date)
    path = _geotiff_dir(cfg) / filename
    if not path.exists():
        raise GeoTiffLoadError(f"No such indicator GeoTIFF: {path}")

    da = rioxarray.open_rasterio(path, masked=True)
    if "band" in da.dims:
        da = da.squeeze("band", drop=True)
    da.attrs = {**da.attrs, "period": period, "indicator": indicator, "product_type": product_type}

    if apply_spi_cap and indicator == "spi" and product_type in ("mean", "median"):
        thresholds_cfg = thresholds_cfg or load_thresholds_config()
        cap = float(thresholds_cfg["spi"]["cap_abs_value"])
        da = _cap_spi(da, cap)

    return da
