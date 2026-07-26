"""PNG quicklook preview generation for GeoTIFF outputs (risk maps, hazard
maps, exposure/vulnerability layers, ...), per project-structure.md's
mapping/export deliverable.

Kept intentionally simple (matplotlib + a geopandas boundary overlay, no
cartopy) -- these are quicklook previews for internal QC/review, not
publication-quality cartographic products.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless -- no display needed to render a PNG file

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from hydroclim_risk.config import PROJECT_ROOT, load_data_config


def save_png_preview(
    array: np.ndarray,
    dest_path: Path | str,
    title: str = "",
    cmap: str = "viridis",
    vmin: float | None = None,
    vmax: float | None = None,
    colorbar_label: str = "",
    domain_cfg: dict[str, Any] | None = None,
    show_admin0_boundary: bool = True,
    category_labels: dict[int, str] | None = None,
) -> Path:
    """Render `array` (on the analysis grid, north-up: row 0 = north,
    matching every GeoTIFF in this project) as a PNG map, with an optional
    Ethiopia admin0 boundary outline.

    `category_labels` (e.g. {0: "None", 1: "Drought", 2: "Wet", 3: "Mixed"})
    switches the colorbar from a continuous scale to discrete ticks -- use
    this for categorical layers (dominant_code, risk_class) where the
    integers are labels, not an ordered magnitude, so a plain numeric
    colorbar would be misleading (e.g. "Wet"=2 is not "twice" "Drought"=1).
    """
    domain_cfg = domain_cfg or load_data_config()
    domain = domain_cfg["domain"]
    extent = [domain["lon_min"], domain["lon_max"], domain["lat_min"], domain["lat_max"]]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(array, extent=extent, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax)
    cbar = fig.colorbar(im, ax=ax, label=colorbar_label)
    if category_labels:
        codes = sorted(category_labels)
        cbar.set_ticks(codes)
        cbar.set_ticklabels([category_labels[c] for c in codes])

    if show_admin0_boundary:
        try:
            from hydroclim_risk.ingestion.boundaries import load_admin_boundaries

            admin0 = load_admin_boundaries(0).to_crs(domain["crs"])
            admin0.boundary.plot(ax=ax, edgecolor="black", linewidth=0.8)
        except Exception:
            pass  # boundary overlay is a nice-to-have, never block the preview on it

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title)

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return dest_path


def preview_geotiff(
    tif_path: Path | str,
    dest_path: Path | str | None = None,
    output_dir: Path | str = "outputs/figures",
    **kwargs: Any,
) -> Path:
    """Read a GeoTIFF and render it as a PNG quicklook via save_png_preview.
    If dest_path isn't given, defaults to output_dir/{tif stem}.png.
    """
    tif_path = Path(tif_path)
    with rasterio.open(tif_path) as src:
        array = src.read(1).astype("float64")
        array = np.where(src.read_masks(1) == 0, np.nan, array) if src.nodata is not None else array

    if dest_path is None:
        out_dir = PROJECT_ROOT / output_dir
        dest_path = out_dir / f"{tif_path.stem}.png"

    kwargs.setdefault("title", tif_path.stem)
    return save_png_preview(array, dest_path, **kwargs)
