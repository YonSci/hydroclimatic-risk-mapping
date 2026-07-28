# Hazards

This page summarizes the hazard component used by the hydroclimatic risk pipeline.

## Hazard dimensions

- Drought hazard: H_dry
- Excess-wetness hazard: H_wet
- Combined hazard: H_overall = max(H_dry, H_wet)

## How hazard is interpreted

- High H_dry means stronger drought signal from SPI, rainfall percentile, CDD, and CWD.
- High H_wet means stronger wetness signal from SPI, rainfall percentile, CWD, Rx1day, and Rx5day.
- H_overall highlights where at least one hazard type is elevated.

## JJAS examples

| H_dry | H_wet |
|---|---|
| ![H_dry JJAS](images/hazard_h_dry_jjas.png) | ![H_wet JJAS](images/hazard_h_wet_jjas.png) |

![H_overall JJAS](images/hazard_h_overall_jjas.png)

## Related outputs

- Probability surfaces (P_drought, P_wet)
- Severity surfaces (S_drought, S_wet)

## Next pages

- For exposure-side context, see [exposure.md](exposure.md).
- For vulnerability-side context, see [vulnerability.md](vulnerability.md).
- For full equations and weights, see [methodology.md](methodology.md).

For equations and standardization rules, see [methodology.md](methodology.md).
