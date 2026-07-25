"""Generate representative PNG quicklooks of each pipeline stage's real
output (Hazard, Probability & Severity, Exposure, Vulnerability, Risk) for
embedding in README.md / docs/. Uses the population sector as the
representative exposure/vulnerability/risk sector throughout, and the
existing export.save_png_preview renderer -- no new rendering logic.

Hazard and Probability & Severity are genuinely period-dependent (they come
from the per-period forecast ensemble), so they're rendered for every
monthly period plus the JJAS season aggregate. Exposure and Vulnerability
are NOT period-dependent in this pipeline (population counts and
socioeconomic/terrain vulnerability don't vary by forecast month) -- each
gets exactly one PNG, not five. Risk is rendered only for JJAS (the
headline seasonal product); see scripts/03_generate_risk_maps.py for the
full period x sector risk batch.

Run:
    python scripts\\04_generate_doc_images.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from hydroclim_risk.config import PROJECT_ROOT, load_data_config, load_thresholds_config  # noqa: E402
from hydroclim_risk.export import save_png_preview  # noqa: E402
from hydroclim_risk.exposure import compute_exposure_layer  # noqa: E402
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
from hydroclim_risk.risk.pipeline import compute_hazard_and_probability_for_period, to_north_up  # noqa: E402
from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code  # noqa: E402
from hydroclim_risk.vulnerability import compute_v_drought, compute_v_wet  # noqa: E402

PERIODS = ["June", "July", "August", "September", "JJAS"]
SECTOR = "population"
IMG_DIR = PROJECT_ROOT / "docs" / "images"


def _slug(period: str) -> str:
    return period.lower()


def generate_hazard_and_probability(period: str, domain_cfg: dict) -> dict[str, np.ndarray]:
    """Compute + render H_dry/H_wet (ensemble mean) and P_drought/P_wet for
    one period. Returns the hazard_prob dict (p_drought/p_wet/s_drought/
    s_wet) so JJAS's call site can reuse it for the Risk stage without
    recomputing.
    """
    slug = _slug(period)
    print(f"  [{period}] Hazard (H_dry, H_wet, H_overall)...")
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
    # the two -- see hazard.py), THEN take the ensemble mean, matching how
    # H_dry_mean/H_wet_mean are each reduced below. This is NOT the same as
    # max(h_dry_mean, h_wet_mean) -- mean-of-max != max-of-means in general.
    h_overall = combine_hazard(h_dry, h_wet)

    # Ensemble-mean H_dry/H_wet/H_overall -- a single representative map per
    # period (H itself is per-member; P/S are what collapse the ensemble
    # downstream).
    h_dry_mean = to_north_up(h_dry.mean(dim="realization"))
    h_wet_mean = to_north_up(h_wet.mean(dim="realization"))
    h_overall_mean = to_north_up(h_overall.mean(dim="realization"))

    save_png_preview(
        h_dry_mean, IMG_DIR / f"hazard_h_dry_{slug}.png",
        title=f"H_dry — {period} 2026 (ensemble mean)", cmap="YlOrBr",
        vmin=0, vmax=1, colorbar_label="H_dry (0-1)", domain_cfg=domain_cfg,
    )
    save_png_preview(
        h_wet_mean, IMG_DIR / f"hazard_h_wet_{slug}.png",
        title=f"H_wet — {period} 2026 (ensemble mean)", cmap="YlGnBu",
        vmin=0, vmax=1, colorbar_label="H_wet (0-1)", domain_cfg=domain_cfg,
    )
    save_png_preview(
        h_overall_mean, IMG_DIR / f"hazard_h_overall_{slug}.png",
        title=f"H_overall = max(H_dry, H_wet) — {period} 2026 (ensemble mean)", cmap="inferno",
        vmin=0, vmax=1, colorbar_label="H_overall (0-1)", domain_cfg=domain_cfg,
    )

    print(f"  [{period}] Probability & Severity (P_drought, P_wet, S_drought, S_wet)...")
    hazard_prob = compute_hazard_and_probability_for_period(period)
    save_png_preview(
        hazard_prob["p_drought"], IMG_DIR / f"probability_p_drought_{slug}.png",
        title=f"P_drought — {period} 2026 (fraction of 25 members)", cmap="YlOrBr",
        vmin=0, vmax=1, colorbar_label="P_drought (0-1)", domain_cfg=domain_cfg,
    )
    save_png_preview(
        hazard_prob["p_wet"], IMG_DIR / f"probability_p_wet_{slug}.png",
        title=f"P_wet — {period} 2026 (fraction of 25 members)", cmap="YlGnBu",
        vmin=0, vmax=1, colorbar_label="P_wet (0-1)", domain_cfg=domain_cfg,
    )
    # S is only defined among members that already cleared the high-hazard
    # threshold (compute_s_drought/wet's event_mask), so its real range is
    # [threshold, 1], not [0, 1] -- use the threshold as vmin so the color
    # scale isn't 40% dead space, instead of copying H/P's vmin=0.
    threshold = load_thresholds_config()["hazard"]["high_hazard_threshold"]
    save_png_preview(
        hazard_prob["s_drought"], IMG_DIR / f"severity_s_drought_{slug}.png",
        title=f"S_drought — {period} 2026 (mean H_dry among drought-classified members)", cmap="YlOrBr",
        vmin=threshold, vmax=1, colorbar_label=f"S_drought ({threshold}-1)", domain_cfg=domain_cfg,
    )
    save_png_preview(
        hazard_prob["s_wet"], IMG_DIR / f"severity_s_wet_{slug}.png",
        title=f"S_wet — {period} 2026 (mean H_wet among wet-classified members)", cmap="YlGnBu",
        vmin=threshold, vmax=1, colorbar_label=f"S_wet ({threshold}-1)", domain_cfg=domain_cfg,
    )
    return hazard_prob


def main() -> None:
    domain_cfg = load_data_config()
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/5 & 2/5] Hazard + Probability & Severity, per period...")
    hazard_prob_by_period = {period: generate_hazard_and_probability(period, domain_cfg) for period in PERIODS}

    print(f"[3/5] Exposure ({SECTOR}) -- static, one PNG (not period-dependent)...")
    e_layer = compute_exposure_layer(SECTOR, domain_cfg=domain_cfg)
    save_png_preview(
        e_layer.normalized, IMG_DIR / "exposure_population.png",
        title="E_population — normalized (0-1, robust 5th/95th percentile)", cmap="viridis",
        vmin=0, vmax=1, colorbar_label="E (0-1)", domain_cfg=domain_cfg,
    )

    print("[4/5] Vulnerability (V_drought, V_wet) -- static, one PNG each...")
    v_drought = compute_v_drought(domain_cfg=domain_cfg)
    v_wet = compute_v_wet(domain_cfg=domain_cfg)
    save_png_preview(
        v_drought, IMG_DIR / "vulnerability_v_drought.png",
        title="V_drought — composite (sensitivity 0.6 + adaptive-capacity deficit 0.4)", cmap="OrRd",
        vmin=0, vmax=1, colorbar_label="V_drought (0-1)", domain_cfg=domain_cfg,
    )
    save_png_preview(
        v_wet, IMG_DIR / "vulnerability_v_wet.png",
        title="V_wet — composite (sensitivity 0.6 + adaptive-capacity deficit 0.4)", cmap="PuBu",
        vmin=0, vmax=1, colorbar_label="V_wet (0-1)", domain_cfg=domain_cfg,
    )

    print(f"[5/5] Risk (R_dominant, risk_class) for {SECTOR}, JJAS only...")
    hazard_prob = hazard_prob_by_period["JJAS"]
    r_drought = compute_risk(hazard_prob["p_drought"], hazard_prob["s_drought"], e_layer.normalized, v_drought)
    r_wet = compute_risk(hazard_prob["p_wet"], hazard_prob["s_wet"], e_layer.normalized, v_wet)
    r_dominant = combine_dominant_risk(r_drought, r_wet)
    risk_class = classify_risk(r_dominant)
    dominant_risk_code(r_drought, r_wet)  # not separately rendered

    save_png_preview(
        r_dominant, IMG_DIR / "risk_r_dominant_population_jjas.png",
        title=f"R_dominant — {SECTOR} sector, JJAS 2026", cmap="YlOrRd",
        vmin=0, vmax=100, colorbar_label="R (0-100)", domain_cfg=domain_cfg,
    )
    save_png_preview(
        risk_class.astype(np.float64), IMG_DIR / "risk_class_population_jjas.png",
        title=f"Risk class — {SECTOR} sector, JJAS 2026", cmap="YlOrRd",
        vmin=0, vmax=4, colorbar_label="Class (0=Very low .. 4=Very high)", domain_cfg=domain_cfg,
    )

    n_written = 7 * len(PERIODS) + 1 + 2 + 2
    print(f"\nWrote {n_written} PNGs to {IMG_DIR}")


if __name__ == "__main__":
    main()
