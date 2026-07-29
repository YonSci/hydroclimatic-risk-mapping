# Results Gallery

Representative outputs from the Ethiopia seasonal run, with the formula and
data behind each stage shown next to its result. Full derivations and weights
are in [methodology.md](methodology.md); component-level detail (data
sources, sub-indicator breakdowns) is in [hazards.md](hazards.md),
[exposure.md](exposure.md), and [vulnerability.md](vulnerability.md).

## Hazard

$$
H_{dry} = 0.35 S_{SPI,dry} + 0.20 S_{rain,dry} + 0.30 S_{CDD,dry} + 0.15 S_{CWD,dry}
\qquad
H_{wet} = 0.20 S_{SPI,wet} + 0.20 S_{rain,wet} + 0.20 S_{CWD,wet} + 0.15 S_{Rx1day,wet} + 0.25 S_{Rx5day,wet}
$$

**Data:** SPI, rainfall percentile, CDD, CWD, Rx1day, Rx5day per ensemble
member, from the sibling indicator-calculation project (see
[data_provenance.md](data_provenance.md)).

### Drought and excess wetness hazard (JJAS)

| H_dry | H_wet |
|---|---|
| ![H_dry JJAS](images/hazard_h_dry_jjas.png) | ![H_wet JJAS](images/hazard_h_wet_jjas.png) |

### Combined hazard (max operator)

$$
H_{overall} = \max(H_{dry}, H_{wet})
$$

![H_overall JJAS](images/hazard_h_overall_jjas.png)

## Probability and Severity

$$
P_{drought} = \frac{\mathrm{count}(H_{dry} \geq 0.60)}{\text{total ensemble members}}
\qquad
S_{drought} = \mathrm{mean}(H_{dry} \text{ among members classified as drought events})
$$

(`P_wet`/`S_wet` are the mirror-image definitions using `H_wet`.) With this
project's 25-member ensemble, probability moves in steps of 1/25 = 4%.

**Data:** same per-member `H_dry`/`H_wet` fields as above, collapsed across
the ensemble dimension.

| P_drought | P_wet |
|---|---|
| ![P_drought JJAS](images/probability_p_drought_jjas.png) | ![P_wet JJAS](images/probability_p_wet_jjas.png) |

| S_drought | S_wet |
|---|---|
| ![S_drought JJAS](images/severity_s_drought_jjas.png) | ![S_wet JJAS](images/severity_s_wet_jjas.png) |

## Vulnerability

$$
V_{drought} = 0.60 (0.5 S_{poverty} + 0.5 S_{aridity}) + 0.40 (0.5 S_{irrigation\_deficit} + 0.5 S_{no\_electricity\_access})
$$

$$
V_{wet} = 0.60 (0.20 S_{poverty} + 0.20 S_{elevation} + 0.20 S_{slope} + 0.20 S_{soil\_clay} + 0.20 S_{river\_distance}) + 0.40 (0.5 S_{healthsites\_deficit} + 0.5 S_{no\_electricity\_access})
$$

**Data:** relative wealth index, aridity index, irrigated-area percent,
population without electricity access, elevation, slope, topsoil clay
content, distance to rivers/water bodies, health facility count -- see
[vulnerability.md](vulnerability.md) for the exact source per indicator.

| V_drought | V_wet |
|---|---|
| ![V_drought](images/vulnerability_v_drought.png) | ![V_wet](images/vulnerability_v_wet.png) |

## Risk

$$
R_{drought} = 100 \cdot P_{drought} \cdot S_{drought} \cdot E \cdot V_{drought}
\qquad
R_{wet} = 100 \cdot P_{wet} \cdot S_{wet} \cdot E \cdot V_{wet}
$$

$$
R_{dominant} = \max(R_{drought}, R_{wet})
$$

$R$ is a relative 0-100 score, **not** a probability percentage, computed per
exposure sector (the figures below use population). Risk class boundaries:

| Range | Class |
|---|---|
| 0-19.9 | Very low |
| 20-39.9 | Low |
| 40-59.9 | Moderate |
| 60-79.9 | High |
| 80-100 | Very high |

**Data:** `P`/`S` from the Hazard/Probability stage above, `E` from
[exposure.md](exposure.md) (population sector, normalized), `V` from the
Vulnerability stage above.

| R_drought | R_wet |
|---|---|
| ![R_drought](images/risk_r_drought_population_jjas.png) | ![R_wet](images/risk_r_wet_population_jjas.png) |

| Dominant risk | Risk class |
|---|---|
| ![R_dominant](images/risk_r_dominant_population_jjas.png) | ![Risk class](images/risk_class_population_jjas.png) |

## Notes

- These figures are rendered products intended for interpretation and communication.
- Full machine-readable outputs are in `outputs/geotiff/` and `outputs/netcdf/`.
- Hazard composition and standardization details are documented in
  [methodology.md](methodology.md).
