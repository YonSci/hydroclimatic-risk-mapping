# Hazards

Hazard is the first term in the pipeline's IPCC-aligned framework,
$R = H \times E \times V$: it describes the climate process itself, before any
question of who or what it affects.

```{admonition} Definition
:class: note
A hazard is a "process, phenomenon or human activity that may cause loss of
life, injury or other health impacts, property damage, social and economic
disruption or environmental degradation" (UNDRR, 2019). This pipeline covers
two hydroclimatic hazard types: seasonal drought and seasonal excess wetness.
```

## In this pipeline

- Drought hazard: `H_dry`
- Excess-wetness hazard: `H_wet`
- Combined hazard: `H_overall = max(H_dry, H_wet)`

- High `H_dry` means a stronger drought signal from SPI, rainfall percentile,
  CDD, and CWD.
- High `H_wet` means a stronger wetness signal from SPI, rainfall percentile,
  CWD, Rx1day, and Rx5day.
- `H_overall` highlights where at least one hazard type is elevated.

Each is a per-ensemble-member field; `H_overall` is combined per member
(`max`) before averaging, not averaged first and then maxed -- see
[methodology.md](methodology.md) for why the order matters.

## Related outputs

- Probability surfaces (`P_drought`, `P_wet`)
- Severity surfaces (`S_drought`, `S_wet`)

## JJAS examples

| H_dry | H_wet |
|---|---|
| ![H_dry JJAS](images/hazard_h_dry_jjas.png) | ![H_wet JJAS](images/hazard_h_wet_jjas.png) |

![H_overall JJAS](images/hazard_h_overall_jjas.png)

## Related documentation

- Full equations, weights, and standardization rules: [methodology.md](methodology.md)
- Exposure component: [exposure.md](exposure.md)
- Vulnerability component: [vulnerability.md](vulnerability.md)
