# Exposure

This page documents the exposure component and where to inspect its source and derived layers.

## Exposure sectors

- Population
- Cropland (total, irrigated, rainfed)
- Livestock
- Built-up surface
- Roads and buildings
- Health facilities

## Notebook inspection references

Exposure details are documented in the notebooks below:

- [Exposure GeoTIFF inspection notebook](../inspect_exposure_geotiffs.html)
- [Raw source inspection notebook](../inspect_exposure_vulnerability_raw_sources.html)

## Exposure workflow

1. Acquire raw sector datasets.
2. Harmonize and resample to the 0.25 degree analysis grid.
3. Preserve absolute layers and generate normalized layers.
4. Feed exposure layers into risk composition with hazard and vulnerability.

## What to look for in the notebooks

### Derived exposure layers (analysis grid)

Use the exposure section in:

- [Exposure GeoTIFF inspection notebook](../inspect_exposure_geotiffs.html)

This notebook includes:

- absolute and normalized exposure rasters
- metadata, units, source, and processing notes
- summary statistics and Ethiopia-clipped map previews

### Raw source layers (pre-resampling)

Use the raw-source section in:

- [Raw source inspection notebook](../inspect_exposure_vulnerability_raw_sources.html)

This notebook includes:

- native-resolution source layers in data/exposure_vulnerability_raw
- source-to-config mapping for exposure indicators
- raw format and extent checks prior to resampling

## Representative figure

![Exposure population example](images/exposure_population.png)

## Related documentation

- Method formulas and composition: [methodology.md](methodology.md)
- Source licensing and caveats: [data_provenance.md](data_provenance.md)
- Vulnerability counterpart: [vulnerability.md](vulnerability.md)
