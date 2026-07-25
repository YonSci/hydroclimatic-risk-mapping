"""Write GeoTIFF outputs for each pipeline stage's representative layer
(Hazard, Probability & Severity, Exposure, Vulnerability, Risk) -- the raster
counterparts of the PNG quicklooks from
scripts/04_generate_doc_images.py, for GIS use rather than documentation.

Uses the same representative period/sector (JJAS 2026, population) as
04_generate_doc_images.py so every file here is directly comparable to the
corresponding image in docs/images/ and to README.md's example maps.

Run:
    python scripts\\05_generate_stage_geotiffs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hydroclim_risk.acquisition.common import write_grid_geotiff  # noqa: E402
from hydroclim_risk.config import PROJECT_ROOT, load_data_config  # noqa: E402
from hydroclim_risk.exposure import compute_exposure_layer, write_exposure_layer  # noqa: E402
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
from hydroclim_risk.ingestion.members import load_member_indicator  # noqa: E402
from hydroclim_risk.risk.pipeline import (  # noqa: E402
    compute_hazard_and_probability_for_period,
    to_north_up,
    write_risk_layers,
)
from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code  # noqa: E402
from hydroclim_risk.vulnerability import compute_v_drought, compute_v_wet  # noqa: E402

PERIOD = "JJAS"
SECTOR = "population"
INIT_DATE = "2026-05-01"


def main() -> None:
    domain_cfg = load_data_config()
    written: list[Path] = []

    print(f"Computing member-level indicators for {PERIOD}...")
    rainfall_p = load_member_indicator(PERIOD, "percentile")
    spi = load_member_indicator(PERIOD, "spi", apply_spi_cap=True)
    cdd_p = load_member_indicator(PERIOD, "cdd")
    cwd_p = load_member_indicator(PERIOD, "cwd")
    rx1_p = load_member_indicator(PERIOD, "rx1day")
    rx5_p = load_member_indicator(PERIOD, "rx5day")

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
    h_dry_mean = to_north_up(h_dry.mean(dim="realization"))
    h_wet_mean = to_north_up(h_wet.mean(dim="realization"))

    print("[1/5] Hazard -> outputs/hazard/...")
    for name, arr in [("h_dry_mean", h_dry_mean), ("h_wet_mean", h_wet_mean)]:
        path = PROJECT_ROOT / "outputs" / "hazard" / f"ethiopia_{PERIOD}_{INIT_DATE}_{name}.tif"
        write_grid_geotiff(
            arr, path, variable=name,
            tags={"period": PERIOD, "init_date": INIT_DATE, "range": "0-1", "reduction": "ensemble_mean"},
            cfg=domain_cfg,
        )
        written.append(path)

    print("[2/5] Probability & Severity -> outputs/probability/...")
    hazard_prob = compute_hazard_and_probability_for_period(PERIOD, init_date=INIT_DATE)
    for name in ["p_drought", "p_wet"]:
        path = PROJECT_ROOT / "outputs" / "probability" / f"ethiopia_{PERIOD}_{INIT_DATE}_{name}.tif"
        write_grid_geotiff(
            hazard_prob[name], path, variable=name,
            tags={"period": PERIOD, "init_date": INIT_DATE, "range": "0-1", "n_members": "25"},
            cfg=domain_cfg,
        )
        written.append(path)

    print(f"[3/5] Exposure ({SECTOR}) -> outputs/exposure/...")
    e_layer = compute_exposure_layer(SECTOR, domain_cfg=domain_cfg)
    written.extend(write_exposure_layer(SECTOR, e_layer, domain_cfg=domain_cfg).values())

    print("[4/5] Vulnerability -> outputs/vulnerability/...")
    v_drought = compute_v_drought(domain_cfg=domain_cfg)
    v_wet = compute_v_wet(domain_cfg=domain_cfg)
    for name, arr in [("v_drought", v_drought), ("v_wet", v_wet)]:
        path = PROJECT_ROOT / "outputs" / "vulnerability" / f"ethiopia_{name}.tif"
        write_grid_geotiff(
            arr, path, variable=name,
            tags={"range": "0-1", "note": "static composite, not period-dependent"},
            cfg=domain_cfg,
        )
        written.append(path)

    print(f"[5/5] Risk ({SECTOR}, {PERIOD}) -> outputs/risk/...")
    r_drought = compute_risk(hazard_prob["p_drought"], hazard_prob["s_drought"], e_layer.normalized, v_drought)
    r_wet = compute_risk(hazard_prob["p_wet"], hazard_prob["s_wet"], e_layer.normalized, v_wet)
    r_dominant = combine_dominant_risk(r_drought, r_wet)
    risk_result = {
        "r_drought": r_drought,
        "r_wet": r_wet,
        "r_dominant": r_dominant,
        "dominant_code": dominant_risk_code(r_drought, r_wet),
        "risk_class": classify_risk(r_dominant),
    }
    written.extend(
        write_risk_layers(PERIOD, SECTOR, risk_result, domain_cfg=domain_cfg, init_date=INIT_DATE).values()
    )

    print(f"\nWrote {len(written)} GeoTIFFs:")
    for path in written:
        print(f"  {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
