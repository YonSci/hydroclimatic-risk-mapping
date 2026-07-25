"""Shared helpers for exposure/vulnerability data acquisition.

Every dataset-specific module in this package (population.py, cropland.py,
livestock.py, poverty.py, irrigation.py) downloads from a real external
source (confirmed working, no-auth-required as of 2026-07-24 — see
config/exposure_data.yaml for the exact URLs) and resamples onto this
project's 0.25 deg Ethiopia analysis grid via the helpers here, so every
exposure/vulnerability layer aligns with the hazard/probability layers
without a separate reprojection step.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from affine import Affine
from rasterio.enums import Resampling
from rasterio.warp import reproject

from hydroclim_risk.config import PROJECT_ROOT, load_data_config

_CHUNK_SIZE = 1 << 20  # 1 MiB
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2


class AcquisitionError(RuntimeError):
    """Raised when a download or resampling step fails."""


_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def download_file(url: str, dest_path: Path | str, overwrite: bool = False, timeout: int = 120) -> Path:
    """Stream-download `url` to `dest_path`. Skips re-downloading if the file
    already exists, unless overwrite=True — acts as a simple local cache for
    the (sometimes large) source files.

    Sends a browser-like User-Agent -- some hosts behind Cloudflare (e.g.
    Mendeley Data, found 2026-07-24) return 403 for the default
    "python-requests" User-Agent but work fine for a real browser string.
    """
    dest_path = Path(dest_path)
    if dest_path.exists() and not overwrite:
        return dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with requests.get(
                url, stream=True, timeout=timeout, headers={"User-Agent": _BROWSER_USER_AGENT}
            ) as resp:
                resp.raise_for_status()
                tmp_path = dest_path.with_name(dest_path.name + ".part")
                with open(tmp_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                        if chunk:
                            fh.write(chunk)
                tmp_path.replace(dest_path)
            return dest_path
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_SECONDS**attempt)

    raise AcquisitionError(f"Failed to download {url} after {_MAX_RETRIES} attempts") from last_exc


def analysis_grid_transform_and_shape(cfg: dict[str, Any] | None = None) -> tuple[Affine, int, int]:
    """(transform, height, width) for the project's 0.25 deg analysis grid,
    north-up (top row = north), matching outputs/geotiff/'s convention.
    """
    cfg = cfg or load_data_config()
    domain = cfg["domain"]
    res = domain["resolution_deg"]
    height, width = domain["grid_shape"]
    transform = Affine(res, 0.0, domain["lon_min"], 0.0, -res, domain["lat_max"])
    return transform, height, width


def reproject_array_to_grid(
    array: np.ndarray,
    src_transform: Affine,
    src_crs: Any,
    resampling: Resampling = Resampling.average,
    src_nodata: float | None = None,
    cfg: dict[str, Any] | None = None,
) -> np.ndarray:
    """Reproject an in-memory 2D array onto the analysis grid."""
    cfg = cfg or load_data_config()
    dst_transform, dst_height, dst_width = analysis_grid_transform_and_shape(cfg)
    dst_crs = cfg["domain"]["crs"]

    destination = np.full((dst_height, dst_width), np.nan, dtype="float64")
    reproject(
        source=array,
        destination=destination,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_resampling=resampling,
        src_nodata=src_nodata,
        dst_nodata=np.nan,
    )
    return destination


_KM_PER_DEGREE_LAT = 111.32


def cell_area_km2(lat_deg: np.ndarray | float, resolution_deg: float) -> np.ndarray | float:
    """Approximate area (km^2) of a lon/lat-aligned grid cell centered at
    lat_deg, using the standard spherical-Earth approximation: 111.32 km per
    degree of latitude, longitude spacing scaled by cos(lat). Accurate to
    within ~0.1% across Ethiopia's latitude range -- sufficient for
    exposure-layer aggregation (WGS84 ellipsoidal precision is not needed
    here).
    """
    return (resolution_deg * _KM_PER_DEGREE_LAT) ** 2 * np.cos(np.radians(lat_deg))


def _row_center_lats(transform: Affine, height: int) -> np.ndarray:
    rows = np.arange(height) + 0.5
    _, lats = transform * (np.zeros(height), rows)
    return np.asarray(lats)


def resample_count_to_grid(
    array: np.ndarray,
    src_transform: Affine,
    src_crs: Any,
    src_resolution_deg: float,
    is_density: bool,
    src_nodata: float | None = None,
    cfg: dict[str, Any] | None = None,
) -> np.ndarray:
    """Resample an extensive count-like layer (population, livestock head
    count) onto the analysis grid while conserving the total.

    GDAL's warp "sum" resampling does NOT do literal block-summation of raw
    pixel values -- verified empirically (2026-07-24): it's still an
    area-weighted combination, so applying it directly to a per-pixel count
    silently shrinks the total by the resampling factor. The correct
    approach for an extensive quantity: convert to a density (count / source
    pixel area) if not already one, average-resample the density (which
    correctly area-weights, see reproject_array_to_grid), then multiply by
    each destination pixel's own area to recover a conserved count.
    """
    array = array.astype("float64")
    if not is_density:
        src_lats = _row_center_lats(src_transform, array.shape[0])
        src_area = cell_area_km2(src_lats, src_resolution_deg)[:, None]
        density = np.where(np.isfinite(array), array / src_area, np.nan)
    else:
        density = array

    dst_density = reproject_array_to_grid(
        density, src_transform, src_crs, resampling=Resampling.average,
        src_nodata=src_nodata, cfg=cfg,
    )

    cfg = cfg or load_data_config()
    dst_transform, dst_height, _ = analysis_grid_transform_and_shape(cfg)
    dst_lats = _row_center_lats(dst_transform, dst_height)
    dst_area = cell_area_km2(dst_lats, cfg["domain"]["resolution_deg"])[:, None]

    return dst_density * dst_area


def reproject_path_to_grid(
    source_path: Path | str,
    band: int = 1,
    resampling: Resampling = Resampling.average,
    cfg: dict[str, Any] | None = None,
) -> np.ndarray:
    """Reproject one band of a raster file directly onto the analysis grid.

    Suitable for sources small/coarse enough to open and warp directly
    (WorldPop, GLW4, GMIA). For very large/high-resolution COGs, prefer
    reading a decimated/windowed array first (see acquisition.cropland) and
    calling reproject_array_to_grid on that instead.
    """
    with rasterio.open(source_path) as src:
        return reproject_array_to_grid(
            array=src.read(band),
            src_transform=src.transform,
            src_crs=src.crs,
            resampling=resampling,
            src_nodata=src.nodata,
            cfg=cfg,
        )


def output_path(dataset_name: str, exposure_cfg: dict[str, Any] | None = None) -> Path:
    """Standard output path for a resampled exposure/vulnerability GeoTIFF."""
    from hydroclim_risk.config import load_yaml

    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    out_dir = PROJECT_ROOT / exposure_cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"ethiopia_{dataset_name}.tif"


def raw_cache_path(filename: str, exposure_cfg: dict[str, Any] | None = None) -> Path:
    """Standard local cache path for a raw downloaded source file."""
    from hydroclim_risk.config import load_yaml

    exposure_cfg = exposure_cfg or load_yaml("exposure_data")
    cache_dir = PROJECT_ROOT / exposure_cfg["raw_cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / filename


def extract_single_file(
    zip_path: Path, extract_dir: Path, suffix: str, name_contains: str | None = None
) -> Path:
    """Extract the one file inside zip_path ending in `suffix` (e.g. '.tif',
    '.asc', '.shp') into extract_dir, and return its path. If the zip
    contains multiple files with that suffix (e.g. two rasters), pass
    `name_contains` to disambiguate by a required substring. Raises
    AcquisitionError if zero or more than one match is found -- ambiguity
    here means the zip's contents changed from what the caller expected.
    """
    with zipfile.ZipFile(zip_path) as zf:
        matches = [n for n in zf.namelist() if n.lower().endswith(suffix.lower())]
        if name_contains is not None:
            matches = [n for n in matches if name_contains.lower() in n.lower()]
        if not matches:
            raise AcquisitionError(
                f"No {suffix} file"
                + (f" containing {name_contains!r}" if name_contains else "")
                + f" found inside {zip_path}"
            )
        if len(matches) > 1:
            raise AcquisitionError(f"Expected exactly one match inside {zip_path}, found {matches}")
        zf.extractall(extract_dir)
    return extract_dir / matches[0]


def write_grid_geotiff(
    array: np.ndarray,
    dest_path: Path | str,
    variable: str,
    tags: dict[str, str] | None = None,
    cfg: dict[str, Any] | None = None,
) -> Path:
    """Write a resampled array to a GeoTIFF on the analysis grid, with a
    provenance tag block matching the convention already used in
    outputs/geotiff/ (index_definition, source, license, etc.).
    """
    cfg = cfg or load_data_config()
    transform, height, width = analysis_grid_transform_and_shape(cfg)
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(
        dest_path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype="float64", crs=cfg["domain"]["crs"], transform=transform, nodata=np.nan,
    ) as dst:
        dst.write(array, 1)
        dst.update_tags(variable=variable, **(tags or {}))

    return dest_path
