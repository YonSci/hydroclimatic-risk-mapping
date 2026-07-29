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

## Formula

Weights below are the live values in `config/weights.yaml`, not illustrative
numbers. Every sub-score is normalized 0-1 first (see "Standardization" below),
then combined by the weighted sum.

$$
H_{dry} = 0.35 \cdot S_{SPI,dry} + 0.20 \cdot S_{rain,dry}
        + 0.30 \cdot S_{CDD,dry} + 0.15 \cdot S_{CWD,dry}
$$

$$
H_{wet} = 0.20 \cdot S_{SPI,wet} + 0.20 \cdot S_{rain,wet}
        + 0.20 \cdot S_{CWD,wet} + 0.15 \cdot S_{Rx1day,wet}
        + 0.25 \cdot S_{Rx5day,wet}
$$

$$
H_{overall} = \max(H_{dry}, H_{wet})
$$

`Rx1day`/`Rx5day` are wetness-only: a low value in either is not meaningful
evidence of dryness, so they never enter `H_dry`. `CDD` is dropped from `H_wet`
for the mirrored reason -- see [methodology.md](methodology.md) for the full
reasoning behind both design calls.

### Standardization (turning a raw indicator into a 0-1 score)

Percentile-based, using each grid cell's own historical distribution for that
calendar period (never a map-wide min-max):

$$
S_{rain,dry} = \mathrm{clip}\!\left(\frac{50 - P}{40},\ 0,\ 1\right), \qquad
S_{SPI,dry} = \mathrm{clip}\!\left(\frac{-SPI}{2},\ 0,\ 1\right)
$$

where $P$ is the rainfall percentile (0-100) at that cell for that calendar
period. `CDD`, `CWD`, `Rx1day`, `Rx5day` use the same clipped-percentile form
against their own historical percentile rank. Full formulas for every
sub-score, see the "Standardization formulas" section in [methodology.md](methodology.md).

### Data used

`H_dry`/`H_wet` are computed per ensemble member from six indicators (rainfall
percentile, SPI, CDD, CWD, Rx1day, Rx5day), produced upstream by the sibling
indicator-calculation project and consumed as trusted input -- see the
"Hazard / probability inputs" table in [data_provenance.md](data_provenance.md)
for the exact source files (`corrected_1993_2025.nc`, `corrected_2026.nc`,
CHIRPS, and the sibling repo's per-period GeoTIFF/NetCDF exports).

### Result

See the JJAS maps below, or the full per-period set (June-September) in
[results_gallery.md](results_gallery.md).

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
