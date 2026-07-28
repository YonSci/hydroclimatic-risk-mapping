# Exposure

Exposure identifies *what* is present in the landscape and *how much of it* sits in
areas where hazard is elevated. It is the second term in the pipeline's
IPCC-aligned framework, $R = H \times E \times V$.

```{admonition} Definition
:class: note
Exposure is "the situation of people, infrastructure, housing, production
capacities and other tangible human assets located in hazard-prone areas"
(UNDRR, 2019). Exposure alone does not imply risk -- it becomes risk only once
combined with hazard and vulnerability.
```

## In this pipeline

Exposure is represented as sector-specific layers on the same 0.25 degree
analysis grid used by hazard and vulnerability, so all three terms can be
multiplied cell-by-cell. Each sector is kept as its own absolute layer
(people, hectares, head count, m^2, km, count) plus a 0-1 normalized layer used
in risk composition -- sectors are never blended into a single generic
"exposure index."

## Exposure sectors and data sources

| Sector | Indicator(s) | Source | License |
|---|---|---|---|
| Population | Population count | WorldPop | CC-BY 4.0 |
| Cropland | Cropland fraction (total, irrigated, rainfed split) | ESA WorldCover 10m v200 (2021) + FAO GMIA v5 | CC-BY 4.0 |
| Livestock | Cattle, sheep, goat head count | FAO Gridded Livestock of the World v4 (2020) | CC-BY 4.0 |
| Built-up surface | Built-up surface area | JRC GHS-BUILT-S R2023A | CC-BY 4.0 |
| Roads and buildings | Road length, building count | OpenStreetMap (via Geofabrik) | ODbL |
| Health facilities | Health facility count | Global Healthsites Mapping Project (via HDX) | ODbL |

Full citations, acquisition modules, and output file names are in
[data_provenance.md](data_provenance.md).

## Exposure workflow

1. Acquire raw sector datasets at native resolution.
2. Harmonize and resample to the 0.25 degree analysis grid (sum for extensive
   quantities like population and built-up area, mean for fractions).
3. Preserve absolute layers and generate normalized (0-1) layers.
4. Feed exposure layers into risk composition with hazard and vulnerability.

## Representative figure

![Exposure population example](images/exposure_population.png)
*Population exposure layer, normalized 0-1, Ethiopia-clipped.*

## Inspect the full layers

Two notebooks carry the complete, machine-readable detail behind this page.
Both are also listed in the left sidebar under this Exposure page.

```{admonition} Exposure GeoTIFF inspection notebook
:class: seealso
[inspect_exposure_geotiffs.html](../inspect_exposure_geotiffs.html) -- absolute
and normalized exposure rasters on the analysis grid: metadata, units, source
and processing notes, summary statistics, and Ethiopia-clipped map previews.
```

```{admonition} Raw source inspection notebook
:class: seealso
[inspect_exposure_vulnerability_raw_sources.html](../inspect_exposure_vulnerability_raw_sources.html)
-- native-resolution source layers from `data/exposure_vulnerability_raw`,
source-to-config mapping, and raw format/extent checks prior to resampling.
```

## Related documentation

- Method formulas and composition: [methodology.md](methodology.md)
- Source licensing and caveats: [data_provenance.md](data_provenance.md)
- Hazard component: [hazards.md](hazards.md)
- Vulnerability component: [vulnerability.md](vulnerability.md)
