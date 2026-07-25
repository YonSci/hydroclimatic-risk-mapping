"""Download IIASA's GDESSA (Gridded Dataset for Electrification in
Sub-Saharan Africa) and resample the "population without electricity
access" density layer onto the analysis grid, conserving total no-access
population count.

Source verified 2026-07-24: Mendeley Data (data.mendeley.com), DOI
10.17632/kn4636mtvg, v6. Direct file URL obtained via Mendeley's public API
(data.mendeley.com/public-api/datasets/kn4636mtvg/files?version=6).
Mendeley's Cloudflare protection returns 403 for Python's `requests` library
specifically (TLS fingerprinting -- not fixable via a browser User-Agent
header, verified) even though curl passes through fine, so this module
downloads via a curl subprocess instead of the shared download_file()
helper.

NetCDF variable Pop_no_access_per_km2 (a density, already people/km^2),
dims (Time (Year) 1-7 representing 2014-2020, Latitude [descending],
Longitude), covering all of Sub-Saharan Africa. Only the latest year
(index 7 / 2020) and Ethiopia's window are used.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
from affine import Affine

from hydroclim_risk.acquisition.common import (
    AcquisitionError,
    output_path,
    raw_cache_path,
    resample_count_to_grid,
    write_grid_geotiff,
)
from hydroclim_risk.config import load_data_config, load_yaml

_CURL_TIMEOUT_SECONDS = 600


def _download_via_curl(url: str, dest_path: Path, overwrite: bool = False) -> Path:
    if dest_path.exists() and not overwrite:
        return dest_path
    if shutil.which("curl") is None:
        raise AcquisitionError("curl is required to download GDESSA (Mendeley blocks Python's requests library)")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_name(dest_path.name + ".part")
    result = subprocess.run(
        ["curl", "-sL", "-o", str(tmp_path), url], timeout=_CURL_TIMEOUT_SECONDS
    )
    if result.returncode != 0 or not tmp_path.exists():
        raise AcquisitionError(f"curl failed to download {url} (exit code {result.returncode})")
    tmp_path.replace(dest_path)
    return dest_path


def download_gdessa(
    exposure_cfg: dict[str, Any] | None = None,
    domain_cfg: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Download, resample, and write the no-electricity-access vulnerability layer."""
    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    domain_cfg = domain_cfg or load_data_config()
    ds_cfg = exposure_cfg["datasets"]["gdessa"]
    domain = domain_cfg["domain"]

    nc_path = raw_cache_path("gdessa_noaccess_ssa_2014_2020.nc", exposure_cfg)
    _download_via_curl(ds_cfg["nc_url"], nc_path, overwrite=overwrite)

    ds = xr.open_dataset(nc_path)
    var = ds[ds_cfg["nc_variable"]]
    time_dim = "Time (Year)"
    latest_year_idx = var.sizes[time_dim] - 1
    da = var.isel({time_dim: latest_year_idx})

    # Latitude is descending in this file -- slice bounds must be given
    # high-to-low to match, unlike an ascending coordinate.
    da = da.sel(Latitude=slice(domain["lat_max"], domain["lat_min"]), Longitude=slice(domain["lon_min"], domain["lon_max"]))

    lats = da["Latitude"].to_numpy()
    lons = da["Longitude"].to_numpy()
    dlon = float(lons[1] - lons[0])
    dlat = float(lats[1] - lats[0])  # negative (descending)
    transform = Affine(dlon, 0, lons[0] - dlon / 2, 0, dlat, lats[0] - dlat / 2)

    density = da.to_numpy().astype("float64")
    density = np.where(density < 0, np.nan, density)

    resampled = resample_count_to_grid(
        density, transform, domain["crs"], src_resolution_deg=abs(dlon), is_density=True, cfg=domain_cfg,
    )

    dest = output_path("gdessa_no_access", exposure_cfg)
    write_grid_geotiff(
        resampled,
        dest,
        variable=ds_cfg["variable"],
        tags={
            "source": ds_cfg["source_name"],
            "license": ds_cfg["license"],
            "citation": ds_cfg["citation"],
            "aggregation": ds_cfg["aggregation"],
            "native_units": ds_cfg["native_units"],
            "year": "2020",
        },
        cfg=domain_cfg,
    )
    return dest
