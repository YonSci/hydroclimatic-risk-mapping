# Hazards

This page summarizes the hazard component used by the hydroclimatic risk pipeline.

## Hazard dimensions

- Drought hazard: H_dry
- Excess-wetness hazard: H_wet
- Combined hazard: H_overall = max(H_dry, H_wet)

## JJAS examples

| H_dry | H_wet |
|---|---|
| ![H_dry JJAS](images/hazard_h_dry_jjas.png) | ![H_wet JJAS](images/hazard_h_wet_jjas.png) |

![H_overall JJAS](images/hazard_h_overall_jjas.png)

## Related outputs

- Probability surfaces (P_drought, P_wet)
- Severity surfaces (S_drought, S_wet)

For equations and standardization rules, see [methodology.md](methodology.md).
