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

- [inspect_exposure_geotiffs.ipynb](../inspect_exposure_geotiffs.ipynb)
- [inspect_exposure_vulnerability_raw_sources.ipynb](../inspect_exposure_vulnerability_raw_sources.ipynb)

## What to look for in the notebooks

### Derived exposure layers (analysis grid)

Use the exposure section in:

- [inspect_exposure_geotiffs.ipynb](../inspect_exposure_geotiffs.ipynb)

This notebook includes:

- absolute and normalized exposure rasters
- metadata, units, source, and processing notes
- summary statistics and Ethiopia-clipped map previews

### Raw source layers (pre-resampling)

Use the raw-source section in:

- [inspect_exposure_vulnerability_raw_sources.ipynb](../inspect_exposure_vulnerability_raw_sources.ipynb)

This notebook includes:

- native-resolution source layers in data/exposure_vulnerability_raw
- source-to-config mapping for exposure indicators
- raw format and extent checks prior to resampling

## Representative figure

![Exposure population example](images/exposure_population.png)
