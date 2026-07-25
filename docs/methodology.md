<!--
Project-local snapshot of the hydroclimatic-risk-mapping skill's methodology
reference, copied 2026-07-25 so the formulas this pipeline implements are
readable without the skill installed. The skill's copy
(.claude/skills/hydroclimatic-risk-mapping/references/methodology.md) is the
canonical source if the two ever diverge -- this file is not auto-synced.
-->

# Methodology Reference

All indicators must be calculated for the **same season, spatial grid, and reference
climatology** (default: 1991–2020, configurable — for the live Ethiopia project this
is 1993–2025, see `project-context.md`). Dry day: rainfall < 1 mm/day (configurable).
Wet day: rainfall ≥ 1 mm/day (configurable).

> **Update note:** The drought-hazard formula below is unchanged from the original
> spec. The excess-wetness formula, the standardization equations, and the
> hazard-combination rule have since been refined (Rx1day/Rx5day promoted from
> "add later" to primary wetness indicators) — see "Excess-wetness hazard (H_wet)
> — updated formula" and the two new sections after it. Use the updated versions
> for new code; the original wetness formula is kept below only for history.

## Core climate indicators

- Seasonal rainfall total
- Standardized Precipitation Index (SPI-3 initially)
- Consecutive Dry Days (CDD)
- Consecutive Wet Days (CWD)

Designed to be extended later with Rx1day, Rx5day, soil moisture, runoff, and river
discharge — add these as new indicator modules, not by modifying the core four.

## Drought hazard (H_drought)

Normalize each indicator to a 0–1 drought score:
- Low rainfall percentile → increases drought hazard
- Negative SPI → increases drought hazard
- High CDD percentile → increases drought hazard
- Low CWD percentile → increases drought hazard

```
H_drought = 0.20 × rainfall_deficit_score
          + 0.35 × SPI_drought_score
          + 0.30 × CDD_drought_score
          + 0.15 × CWD_drought_score
```

## Excess-wetness hazard (H_wet) — original formula (superseded, kept for history)

Normalize each indicator to a 0–1 wetness score:
- High rainfall percentile → increases wetness hazard
- Positive SPI → increases wetness hazard
- High CWD percentile → increases wetness hazard
- Low CDD percentile → supporting evidence only, low weight

```
H_wet = 0.25 × high_rainfall_score
      + 0.30 × positive_SPI_score
      + 0.35 × CWD_wetness_score
      + 0.10 × low_CDD_score
```

Normalize rainfall total, CDD, and CWD using **percentile-based normalization**
(not map-specific min-max) so results are comparable across years and forecast
initializations.

## Excess-wetness hazard (H_wet) — updated formula (use this one)

CWD measures persistence but not intensity — it won't catch a flood-producing
short, intense burst of rain. Rx1day (max 1-day rainfall) and Rx5day (max
consecutive 5-day rainfall) are now primary indicators instead of a later
extension. CDD is dropped from the wetness formula (a low CDD isn't strong
independent evidence of wetness once CWD, SPI, and rainfall percentile are
already included — keeping it risked padding the score with a redundant signal).

```
H_wet = 0.20 × SPI_wet_score
      + 0.20 × rainfall_percentile_wet_score
      + 0.20 × CWD_wet_score
      + 0.15 × Rx1day_wet_score
      + 0.25 × Rx5day_wet_score
```

Weights sum to 1.00. Rx5day gets the largest single weight because accumulated
multi-day rainfall is particularly relevant to soil saturation and waterlogging.
Rx1day and Rx5day should **not** be used for drought (a low value there isn't
meaningful evidence of dryness) — keep them wetness-only.

## Drought hazard (H_dry) — same formula, just renamed for consistency

The project now refers to this as `H_dry` (equivalent to `H_drought` above) to
pair naturally with `H_wet`. The formula and weights are unchanged:

```
H_dry = 0.35 × SPI_dry_score
      + 0.20 × rainfall_percentile_dry_score
      + 0.30 × CDD_dry_score
      + 0.15 × CWD_dry_score
```

Do **not** add Rx1day/Rx5day to the drought formula — a low value in either isn't
meaningful evidence of dryness, so they stay wetness-only.

## Standardization formulas

Use **local, calendar-period-specific** historical distributions — June 2026
compares against historical Junes, JJAS 2026 against historical JJAS seasons, etc.
Never mix calendar periods when computing a percentile rank.

**Rainfall percentile** (`P` = rainfall percentile, 0–100, at that grid cell for
that calendar period):

```
S_rain_dry = clip((50 − P) / 40, 0, 1)   # 10th percentile or below → max drought score
S_rain_wet = clip((P − 50) / 40, 0, 1)   # 90th percentile or above → max wetness score
```

Near the 50th percentile, both scores are ~0 (no hazard contribution).

**SPI** (standardized value, roughly −3 to +3):

```
S_SPI_dry = clip(−SPI / 2, 0, 1)
S_SPI_wet = clip(SPI / 2, 0, 1)
```

Reference points: SPI = −2.0 → dry score 1.00; SPI = −1.0 → dry score 0.50;
SPI = +1.0 → wet score 0.50; SPI = +2.0 → wet score 1.00.

**CDD, CWD, Rx1day, Rx5day** — use each index's own historical percentile rank
`p` at that grid cell for that calendar period (not the raw value, not map-wide
min-max):

```
S_CDD_dry   = clip((p_CDD − 50) / 40, 0, 1)   # high CDD percentile → dry
S_CWD_dry   = clip((50 − p_CWD) / 40, 0, 1)   # low CWD percentile → dry
S_CWD_wet   = clip((p_CWD − 50) / 40, 0, 1)   # high CWD percentile → wet
S_Rx1day_wet = clip((p_Rx1day − 50) / 40, 0, 1)
S_Rx5day_wet = clip((p_Rx5day − 50) / 40, 0, 1)
```

## Combining drought and wetness into overall hazard — use max, not average

Never average `H_dry` and `H_wet` — opposite hazard signals would cancel each
other and mask a real hazard. Instead:

```
H_overall = max(H_dry, H_wet)
```

Dominant-hazard categorical layer `T` (same codes as the `R_dominant` categorical
layer used later in the risk step — keep them consistent):

```
T = 0   if neither H_dry nor H_wet is substantial (below the high-hazard threshold)
T = 1   if H_dry > H_wet  (drought-dominated)
T = 2   if H_wet > H_dry  (wetness-dominated)
T = 3   if both hazards are substantial (mixed/compound)
```

## Hazard probability

Input data has either `year × lat × lon` (historical) or
`ensemble_member × lat × lon` (forecast) dimensions. High-hazard threshold:
configurable, default 0.60.

```
P_drought = count(H_drought ≥ 0.60) / total_valid_realizations
P_wet     = count(H_wet ≥ 0.60) / total_valid_realizations
P_any     = count(H_drought ≥ 0.60 OR H_wet ≥ 0.60) / total_valid_realizations
```

With a 25-member ensemble (this project's default), probability moves in
increments of 1/25 = 0.04 = 4% — don't report finer precision than that implies.

**Caveat:** don't confuse a pre-existing "SPI drought probability" or "SPI wet
probability" product (P(SPI ≤ −1.0) or P(SPI ≥ +1.0), computed from SPI alone)
with the full composite `P_dry`/`P_wet` defined here. The composite probability
must be computed from the member-level `H_dry`/`H_wet` hazard scores (which blend
SPI with rainfall percentile, CDD/CWD, and Rx1day/Rx5day), not from SPI in
isolation. If an existing GeoTIFF is named like a probability product, check what
it was actually computed from before wiring it into `P_dry`/`P_wet`.

Also calculate the probability of joint drought+wetness events within the selected
assessment period when both can occur, and conditional severity:

```
S_drought = mean(H_drought among realizations classified as drought events)
S_wet     = mean(H_wet among realizations classified as wetness events)
```

## Exposure

Separate maps for: population, rainfed cropland, irrigated cropland, crop
production, livestock, roads, health facilities, water infrastructure,
settlements, economic assets.

Maintain both:
- **Absolute exposure** (people, hectares, livestock head, etc.)
- **Normalized exposure index** (0–1), using robust 5th/95th-percentile
  normalization

Do not combine incompatible physical units into one index unless a clearly
documented composite exposure index is explicitly requested by the user.

## Drought vulnerability (V_drought)

**Sensitivity indicators:** rainfed-agriculture dependence, drought-sensitive crop
area, historical yield variability, low soil water-holding capacity, land
degradation, water scarcity, poverty, food insecurity, livestock dependence.

**Adaptive-capacity indicators:** irrigation access, water storage, functional
water points, climate-information access, agricultural extension access,
drought-tolerant seed access, credit, insurance, livelihood diversification,
market access, social protection.

Normalize all to 0–1; reverse beneficial indicators so higher = more vulnerable.

```
V_drought = 0.60 × drought_sensitivity + 0.40 × adaptive_capacity_deficit
```

## Excess-wetness vulnerability (V_wet)

**Sensitivity indicators:** poorly drained soils, low-lying terrain, topographic
wetness, proximity to rivers, waterlogging-sensitive crops, historical wetness
losses, erosion susceptibility, landslide susceptibility, poor housing,
unpaved-road dependence, weak sanitation.

**Adaptive-capacity indicators:** agricultural drainage, urban drainage,
flood-protection structures, all-weather roads, improved storage, short-range
forecast access, emergency-response capacity, health-service access, crop
insurance, disease surveillance.

```
V_wet = 0.60 × wetness_sensitivity + 0.40 × adaptive_capacity_deficit
```

## Risk calculation

```
R_drought = 100 × P_drought × S_drought × E_drought × V_drought
R_wet     = 100 × P_wet × S_wet × E_wet × V_wet
```

These are relative 0–100 risk scores, **not** probability percentages.

```
R_dominant = max(R_drought, R_wet)
```

Categorical dominant-risk layer:
- 0 = insignificant / no identified risk
- 1 = drought-dominated risk
- 2 = excess-wetness-dominated risk
- 3 = mixed / compound risk (where applicable)

### Member-wise (ensemble) risk

When ensemble data are available:

```
member_drought_risk = drought_event × drought_severity × drought_exposure × drought_vulnerability
member_wetness_risk = wetness_event × wetness_severity × wetness_exposure × wetness_vulnerability
```

Per member, overall risk = `max(member_drought_risk, member_wetness_risk)` unless
cumulative impacts are explicitly requested. Average the member-wise overall risk
across all members for the final ensemble risk map.

## Risk classes (configurable)

| Range     | Class      |
|-----------|------------|
| 0–19.9    | Very low   |
| 20–39.9   | Low        |
| 40–59.9   | Moderate   |
| 60–79.9   | High       |
| 80–100    | Very high  |

The architecture must support later calibration against observed crop losses,
livestock mortality, water shortages, waterlogging, and infrastructure-damage
records — keep calibration as a pluggable step, not baked into the risk formula.
