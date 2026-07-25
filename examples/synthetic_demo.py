"""Reproducible end-to-end demo of the hydroclim_risk pipeline using
synthetic data -- no real downloads required (no forecast NetCDF, no
exposure/vulnerability GeoTIFFs). Demonstrates every stage: hazard scoring,
probability/severity, exposure normalization, vulnerability combination, and
final risk calculation, using the exact same functions the real pipeline
uses (see scripts/03_generate_risk_maps.py for the real-data equivalent).

The only real project data used is boundaries/eth_shapefile/ -- a small,
bundled project asset (not a download), used for the map preview's
admin0 outline and vulnerability's gap-filling mask.

Run:
    python examples\\synthetic_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import xarray as xr  # noqa: E402
from affine import Affine  # noqa: E402

from hydroclim_risk.config import load_data_config, load_yaml  # noqa: E402
from hydroclim_risk.exposure import compute_exposure_layer  # noqa: E402
from hydroclim_risk.export import save_png_preview  # noqa: E402
from hydroclim_risk.hazard import (  # noqa: E402
    cdd_dry_score,
    compute_h_dry,
    compute_h_wet,
    cwd_dry_score,
    cwd_wet_score,
    rainfall_percentile_dry_score,
    rainfall_percentile_wet_score,
    rx1day_wet_score,
    rx5day_wet_score,
    spi_dry_score,
    spi_wet_score,
)
from hydroclim_risk.probability import compute_p_drought, compute_p_wet, compute_s_drought, compute_s_wet  # noqa: E402
from hydroclim_risk.risk.pipeline import to_north_up  # noqa: E402
from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code  # noqa: E402
from hydroclim_risk.vulnerability import compute_v_drought, compute_v_wet  # noqa: E402


def make_synthetic_member_indicator(
    domain: dict[str, Any], n_realization: int, rng: np.random.Generator, kind: str
) -> xr.DataArray:
    """A small (lat, lon, realization) DataArray mimicking
    ingestion.members' real output -- ascending latitude, matching the raw
    NetCDF convention (see risk/pipeline.py's docstring on why this matters).
    """
    res = domain["resolution_deg"]
    lat = np.arange(domain["lat_min"] + res / 2, domain["lat_max"], res)
    lon = np.arange(domain["lon_min"] + res / 2, domain["lon_max"], res)
    shape = (len(lat), len(lon), n_realization)
    if kind == "spi":
        data = rng.normal(loc=-0.5, scale=1.2, size=shape)  # centered slightly dry, for a visible signal
    else:  # percentile-type indicator, 0-100
        data = rng.uniform(0, 100, size=shape)
    return xr.DataArray(
        data,
        dims=("lat", "lon", "realization"),
        coords={"lat": lat, "lon": lon, "realization": np.arange(n_realization)},
    )


def make_synthetic_exposure_vulnerability_dir(domain: dict[str, Any], rng: np.random.Generator) -> Path:
    """A temp directory of tiny synthetic exposure/vulnerability GeoTIFFs,
    using the exact filenames exposure/ and vulnerability/ expect.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="hydroclim_synthetic_"))
    res = domain["resolution_deg"]
    height, width = domain["grid_shape"]
    transform = Affine(res, 0, domain["lon_min"], 0, -res, domain["lat_max"])

    def write(name: str, arr: np.ndarray) -> None:
        with rasterio.open(
            tmp_dir / name, "w", driver="GTiff", height=height, width=width, count=1,
            dtype="float64", crs=domain["crs"], transform=transform,
        ) as dst:
            dst.write(arr.astype("float64"), 1)

    write("ethiopia_population.tif", rng.uniform(100, 50_000, (height, width)))
    write("ethiopia_cropland.tif", rng.uniform(0, 1, (height, width)))
    write("ethiopia_irrigation_gmia.tif", rng.uniform(0, 30, (height, width)))
    write("ethiopia_livestock_cattle.tif", rng.uniform(0, 10_000, (height, width)))
    write("ethiopia_buildings.tif", rng.integers(0, 500, (height, width)))
    write("ethiopia_roads.tif", rng.uniform(0, 100, (height, width)))
    write("ethiopia_healthsites.tif", rng.integers(0, 5, (height, width)))
    write("ethiopia_ghs_built.tif", rng.uniform(0, 1_000_000, (height, width)))
    write("ethiopia_poverty_rwi.tif", rng.normal(-0.3, 0.5, (height, width)))
    write("ethiopia_aridity.tif", rng.uniform(0.1, 0.8, (height, width)))
    write("ethiopia_gdessa_no_access.tif", rng.uniform(0, 20_000, (height, width)))
    return tmp_dir


def main() -> None:
    rng = np.random.default_rng(42)
    domain_cfg = load_data_config()
    domain = domain_cfg["domain"]

    print("=" * 70)
    print("HYDROCLIM_RISK SYNTHETIC DEMO -- no real forecast/exposure data required")
    print("=" * 70)

    print("\n[1/4] Synthetic member-level indicators -> hazard -> probability...")
    n_members = 25
    rainfall_p = make_synthetic_member_indicator(domain, n_members, rng, "percentile")
    spi = make_synthetic_member_indicator(domain, n_members, rng, "spi")
    cdd_p = make_synthetic_member_indicator(domain, n_members, rng, "percentile")
    cwd_p = make_synthetic_member_indicator(domain, n_members, rng, "percentile")
    rx1_p = make_synthetic_member_indicator(domain, n_members, rng, "percentile")
    rx5_p = make_synthetic_member_indicator(domain, n_members, rng, "percentile")

    h_dry = compute_h_dry(
        {
            "spi_dry_score": spi_dry_score(spi),
            "rainfall_percentile_dry_score": rainfall_percentile_dry_score(rainfall_p),
            "cdd_dry_score": cdd_dry_score(cdd_p),
            "cwd_dry_score": cwd_dry_score(cwd_p),
        }
    )
    h_wet = compute_h_wet(
        {
            "spi_wet_score": spi_wet_score(spi),
            "rainfall_percentile_wet_score": rainfall_percentile_wet_score(rainfall_p),
            "cwd_wet_score": cwd_wet_score(cwd_p),
            "rx1day_wet_score": rx1day_wet_score(rx1_p),
            "rx5day_wet_score": rx5day_wet_score(rx5_p),
        }
    )

    p_drought = to_north_up(compute_p_drought(h_dry))
    p_wet = to_north_up(compute_p_wet(h_wet))
    s_drought = to_north_up(compute_s_drought(h_dry))
    s_wet = to_north_up(compute_s_wet(h_wet))
    print(f"  P_drought mean={np.nanmean(p_drought):.3f}   P_wet mean={np.nanmean(p_wet):.3f}")

    print("\n[2/4] Synthetic exposure/vulnerability layers...")
    ev_dir = make_synthetic_exposure_vulnerability_dir(domain, rng)
    exposure_cfg = {**load_yaml("exposure_data"), "output_dir": str(ev_dir)}
    print(f"  wrote synthetic GeoTIFFs to {ev_dir}")

    e_layer = compute_exposure_layer("population", exposure_cfg=exposure_cfg, domain_cfg=domain_cfg)
    v_drought = compute_v_drought(exposure_cfg=exposure_cfg, domain_cfg=domain_cfg)
    v_wet = compute_v_wet(exposure_cfg=exposure_cfg, domain_cfg=domain_cfg)
    print(f"  E(population) mean={np.nanmean(e_layer.normalized):.3f}")
    print(f"  V_drought mean={np.nanmean(v_drought):.3f}   V_wet mean={np.nanmean(v_wet):.3f}")

    print("\n[3/4] Risk = 100 * P * S * E * V...")
    r_drought = compute_risk(p_drought, s_drought, e_layer.normalized, v_drought)
    r_wet = compute_risk(p_wet, s_wet, e_layer.normalized, v_wet)
    r_dominant = combine_dominant_risk(r_drought, r_wet)
    classify_risk(r_dominant)
    dominant_risk_code(r_drought, r_wet)

    print(f"  R_drought: min={np.nanmin(r_drought):.2f} max={np.nanmax(r_drought):.2f} mean={np.nanmean(r_drought):.2f}")
    print(f"  R_wet:     min={np.nanmin(r_wet):.2f} max={np.nanmax(r_wet):.2f} mean={np.nanmean(r_wet):.2f}")

    print("\n[4/4] Rendering a PNG preview...")
    out_path = Path("outputs/figures/synthetic_demo_r_dominant.png")
    save_png_preview(
        r_dominant, out_path, title="Synthetic demo: R_dominant (population sector)",
        colorbar_label="R (0-100)", cmap="YlOrRd", domain_cfg=domain_cfg,
    )
    print(f"  wrote {out_path}")

    print(
        "\nDone -- this demonstrates the full hazard -> probability -> exposure -> "
        "vulnerability -> risk chain end-to-end with no real forecast/exposure data files."
    )


if __name__ == "__main__":
    main()
