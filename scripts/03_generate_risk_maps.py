"""Generate full risk maps: loop over every forecast period x exposure
sector, compute R_drought/R_wet/R_dominant/dominant_code/risk_class, and
write them all to outputs/risk/.

Vulnerability (V_drought/V_wet) is static and computed once, shared across
every period and sector. Hazard/probability (P/S) is period-specific and
computed once per period, shared across every sector in that period --
avoids recomputing the same member-level indicator load + hazard scoring 9x
(once per sector) when it only needs to happen once per period.

Usage:
    python scripts\\03_generate_risk_maps.py
    python scripts\\03_generate_risk_maps.py --periods June,JJAS --sectors population,cropland_total
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hydroclim_risk.config import load_data_config, load_yaml  # noqa: E402
from hydroclim_risk.exposure import compute_exposure_layer  # noqa: E402
from hydroclim_risk.risk.pipeline import compute_hazard_and_probability_for_period, write_risk_layers  # noqa: E402
from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code  # noqa: E402
from hydroclim_risk.vulnerability import compute_v_drought, compute_v_wet  # noqa: E402

ALL_PERIODS = ["June", "July", "August", "September", "JJAS"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--periods", type=str, default=None, help=f"Comma-separated subset of {ALL_PERIODS} (default: all)."
    )
    parser.add_argument(
        "--sectors", type=str, default=None,
        help="Comma-separated subset of exposure sectors (default: all in config/exposure_indicators.yaml).",
    )
    args = parser.parse_args()

    domain_cfg = load_data_config()
    exp_ind_cfg = load_yaml("exposure_indicators")
    all_sectors = list(exp_ind_cfg["layers"])

    periods = args.periods.split(",") if args.periods else ALL_PERIODS
    sectors = args.sectors.split(",") if args.sectors else all_sectors

    unknown_periods = set(periods) - set(ALL_PERIODS)
    unknown_sectors = set(sectors) - set(all_sectors)
    if unknown_periods:
        parser.error(f"Unknown period(s): {sorted(unknown_periods)}. Choose from {ALL_PERIODS}.")
    if unknown_sectors:
        parser.error(f"Unknown sector(s): {sorted(unknown_sectors)}. Choose from {all_sectors}.")

    print("=" * 70)
    print("RISK MAP GENERATION")
    print("=" * 70)
    print(f"periods: {periods}")
    print(f"sectors: {sectors}")

    print("\nComputing vulnerability (static, shared across every period/sector)...")
    t0 = time.time()
    v_drought = compute_v_drought(domain_cfg=domain_cfg)
    v_wet = compute_v_wet(domain_cfg=domain_cfg)
    print(f"  done ({time.time() - t0:.1f}s)")

    failed: list[str] = []
    n_written = 0
    for period in periods:
        print(f"\n--- {period}: computing hazard/probability ---")
        t0 = time.time()
        try:
            hazard_prob = compute_hazard_and_probability_for_period(period)
        except Exception as exc:
            print(f"[FAILED] {period} hazard/probability: {exc}")
            failed.append(f"{period} (hazard/probability)")
            continue
        print(f"  done ({time.time() - t0:.1f}s)")

        for sector in sectors:
            key = f"{period}/{sector}"
            try:
                e_layer = compute_exposure_layer(sector, domain_cfg=domain_cfg)
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
                written = write_risk_layers(period, sector, risk_result, domain_cfg=domain_cfg)
                n_written += len(written)
                print(f"  [OK] {key} -> {len(written)} files")
            except Exception as exc:
                print(f"  [FAILED] {key}: {exc}")
                failed.append(key)

    print("-" * 70)
    print(f"Wrote {n_written} risk GeoTIFFs to outputs/risk/.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1
    print("All risk maps generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
