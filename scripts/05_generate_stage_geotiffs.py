"""Write GeoTIFF outputs for each pipeline stage's representative layer
(Hazard, Probability & Severity, Exposure, Vulnerability, Risk) -- the raster
counterparts of scripts/04_generate_doc_images.py's PNG quicklooks, for GIS
use rather than documentation.

Hazard and Probability & Severity are genuinely period-dependent, so they're
written for every monthly period plus the JJAS season aggregate. Exposure
and Vulnerability are NOT period-dependent in this pipeline -- each gets
exactly one GeoTIFF, not five (see 04_generate_doc_images.py's docstring).
Risk is written only for JJAS (the headline seasonal product); see
scripts/03_generate_risk_maps.py for the full period x sector risk batch
already in outputs/risk/.

Run:
    python scripts\\05_generate_stage_geotiffs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hydroclim_risk.acquisition.common import write_grid_geotiff  # noqa: E402
from hydroclim_risk.config import PROJECT_ROOT, load_data_config, load_thresholds_config  # noqa: E402
from hydroclim_risk.exposure import compute_exposure_layer, write_exposure_layer  # noqa: E402
from hydroclim_risk.hazard import (  # noqa: E402
    cdd_dry_score,
    combine_hazard,
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

PERIODS = ["June", "July", "August", "September", "JJAS"]
SECTOR = "population"
INIT_DATE = "2026-05-01"


def generate_hazard_and_probability(period: str, domain_cfg: dict) -> tuple[dict, list[Path]]:
    written: list[Path] = []
    rainfall_p = load_member_indicator(period, "percentile")
    spi = load_member_indicator(period, "spi", apply_spi_cap=True)
    cdd_p = load_member_indicator(period, "cdd")
    cwd_p = load_member_indicator(period, "cwd")
    rx1_p = load_member_indicator(period, "rx1day")
    rx5_p = load_member_indicator(period, "rx5day")

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
    # H_overall = max(H_dry, H_wet) PER MEMBER (combine_hazard never averages
    # the two), THEN ensemble mean -- see 04_generate_doc_images.py's comment
    # on why this differs from max(h_dry_mean, h_wet_mean).
    h_overall = combine_hazard(h_dry, h_wet)

    h_dry_mean = to_north_up(h_dry.mean(dim="realization"))
    h_wet_mean = to_north_up(h_wet.mean(dim="realization"))
    h_overall_mean = to_north_up(h_overall.mean(dim="realization"))

    for name, arr in [
        ("h_dry_mean", h_dry_mean), ("h_wet_mean", h_wet_mean), ("h_overall_mean", h_overall_mean),
    ]:
        path = PROJECT_ROOT / "outputs" / "hazard" / f"ethiopia_{period}_{INIT_DATE}_{name}.tif"
        write_grid_geotiff(
            arr, path, variable=name,
            tags={"period": period, "init_date": INIT_DATE, "range": "0-1", "reduction": "ensemble_mean"},
            cfg=domain_cfg,
        )
        written.append(path)

    hazard_prob = compute_hazard_and_probability_for_period(period, init_date=INIT_DATE)
    for name in ["p_drought", "p_wet"]:
        path = PROJECT_ROOT / "outputs" / "probability" / f"ethiopia_{period}_{INIT_DATE}_{name}.tif"
        write_grid_geotiff(
            hazard_prob[name], path, variable=name,
            tags={"period": period, "init_date": INIT_DATE, "range": "0-1", "n_members": "25"},
            cfg=domain_cfg,
        )
        written.append(path)

    # S is only defined among members that cleared the high-hazard threshold
    # (its real range is [threshold, 1], not [0, 1]) -- record that in the tag
    # rather than letting a downstream reader assume a 0-1 range like P/H.
    threshold = load_thresholds_config()["hazard"]["high_hazard_threshold"]
    for name in ["s_drought", "s_wet"]:
        path = PROJECT_ROOT / "outputs" / "probability" / f"ethiopia_{period}_{INIT_DATE}_{name}.tif"
        write_grid_geotiff(
            hazard_prob[name], path, variable=name,
            tags={
                "period": period, "init_date": INIT_DATE,
                "range": f"{threshold}-1 (NaN where no member qualifies as an event)",
            },
            cfg=domain_cfg,
        )
        written.append(path)

    return hazard_prob, written


def main() -> None:
    domain_cfg = load_data_config()
    written: list[Path] = []

    print("[1/5 & 2/5] Hazard + Probability & Severity, per period...")
    hazard_prob_by_period: dict[str, dict] = {}
    for period in PERIODS:
        print(f"  Computing member-level indicators for {period}...")
        hazard_prob, paths = generate_hazard_and_probability(period, domain_cfg)
        hazard_prob_by_period[period] = hazard_prob
        written.extend(paths)

    print(f"[3/5] Exposure ({SECTOR}) -- static, one GeoTIFF (not period-dependent)...")
    e_layer = compute_exposure_layer(SECTOR, domain_cfg=domain_cfg)
    written.extend(write_exposure_layer(SECTOR, e_layer, domain_cfg=domain_cfg).values())

    print("[4/5] Vulnerability -- static, one GeoTIFF each...")
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

    print(f"[5/5] Risk ({SECTOR}, JJAS only) -> outputs/risk/...")
    hazard_prob = hazard_prob_by_period["JJAS"]
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
        write_risk_layers("JJAS", SECTOR, risk_result, domain_cfg=domain_cfg, init_date=INIT_DATE).values()
    )

    print(f"\nWrote {len(written)} GeoTIFFs:")
    for path in written:
        print(f"  {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
