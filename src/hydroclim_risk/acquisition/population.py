"""Download WorldPop's Ethiopia population-count raster and resample it onto
the analysis grid, conserving the national total.

Source verified 2026-07-24: WorldPop's REST API
(https://hub.worldpop.org/rest/data/pop/wpgp?iso3=ETH) returns a list of
yearly datasets, each with a direct, no-auth GeoTIFF download URL under
data.worldpop.org (e.g. .../ETH/eth_ppp_2020.tif). Units are people per
source pixel (~100m) -- an extensive count, not a density, so
resample_count_to_grid(is_density=False) is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests

from hydroclim_risk.acquisition.common import (
    AcquisitionError,
    download_file,
    output_path,
    raw_cache_path,
    resample_count_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_yaml


def _latest_worldpop_file_url(api_url: str, timeout: int = 60) -> tuple[str, str]:
    """Query WorldPop's REST API and return (download_url, popyear) for the
    most recently available year's Ethiopia population-count dataset.
    """
    resp = requests.get(api_url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        raise AcquisitionError(f"WorldPop API returned no datasets for {api_url}")

    latest = max(data, key=lambda d: int(d["popyear"]))
    files = latest.get("files") or []
    if not files:
        raise AcquisitionError(f"WorldPop entry for year {latest.get('popyear')} has no file URL")
    return files[0], str(latest["popyear"])


def download_population(exposure_cfg: dict[str, Any] | None = None, overwrite: bool = False) -> Path:
    """Download, resample, and write the population-count exposure layer.

    Returns the path to the written GeoTIFF (outputs/exposure_vulnerability/
    ethiopia_population.tif), with the national total preserved through
    resampling.
    """
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    ds_cfg = exposure_cfg["datasets"]["population"]

    url, popyear = _latest_worldpop_file_url(ds_cfg["api_url"])
    raw_path = raw_cache_path(f"worldpop_eth_ppp_{popyear}.tif", exposure_cfg)
    download_file(url, raw_path, overwrite=overwrite)

    with rasterio.open(raw_path) as src:
        counts = src.read(1).astype("float64")
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
        src_res_deg = abs(transform.a)

    if nodata is not None:
        counts = np.where(counts == nodata, np.nan, counts)
    counts = np.where(counts < 0, np.nan, counts)  # WorldPop uses negative sentinels at sea/nodata edges

    resampled = resample_count_to_grid(
        counts, transform, crs, src_resolution_deg=src_res_deg, is_density=False,
    )

    dest = output_path("population", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "popyear": popyear,
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "units": ds_cfg["absolute_units"],
        },
    )
    return dest
