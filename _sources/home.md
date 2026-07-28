# Hydroclimatic Risk Mapping - Ethiopia

This documentation presents a reproducible, config-driven pipeline for seasonal
hydroclimatic risk mapping over Ethiopia using the IPCC-aligned framework:

$$
R = H \times E \times V
$$

where:
- $H$ is hazard (drought or excess wetness)
- $E$ is exposure (people, cropland, livestock, infrastructure)
- $V$ is vulnerability

<section class="hero">
  <div class="hero-inner">
    <p class="hero-kicker">Seasonal Forecast Analytics</p>
    <h2 class="hero-title">From Ensemble Rainfall Forecasts To Actionable Risk Maps</h2>
    <p class="hero-subtitle">
      A country-scale risk-screening workflow for Ethiopia that combines hazard,
      exposure, and vulnerability into interpretable outputs for planning,
      preparedness, and communication.
    </p>
  </div>
</section>

## What you can do with this documentation

<div class="tool-grid">
  <a class="tool-card" href="docs/hazards.html">
    <h3>Hazards</h3>
    <p>Inspect drought and excess-wetness hazard construction and JJAS hazard products.</p>
  </a>
  <a class="tool-card" href="docs/exposure.html">
    <h3>Exposure</h3>
    <p>Review sectoral exposure layers with notebook-based raw and derived inspections.</p>
  </a>
  <a class="tool-card" href="docs/vulnerability.html">
    <h3>Vulnerability</h3>
    <p>Explore drought and wetness vulnerability composition and supporting indicators.</p>
  </a>
  <a class="tool-card" href="docs/results_gallery.html">
    <h3>Results Gallery</h3>
    <p>View representative hazard, probability, severity, and risk map outputs.</p>
  </a>
</div>

## Documentation map

<div class="doc-grid">
  <a class="doc-pill" href="docs/methodology.html">Methodology</a>
  <a class="doc-pill" href="docs/data_provenance.html">Data Provenance</a>
  <a class="doc-pill" href="docs/reproducibility.html">Reproducibility</a>
  <a class="doc-pill" href="inspect_exposure_geotiffs.html">Exposure GeoTIFF Notebook</a>
  <a class="doc-pill" href="inspect_exposure_vulnerability_raw_sources.html">Raw Source Notebook</a>
</div>

## Pipeline at a glance

```mermaid
flowchart LR
  A[Bias-corrected ensemble and CHIRPS] --> B[Hazard indices and standardization]
  B --> C[Hazard H_dry and H_wet]
  C --> D[Probability P and Severity S]
  E[Exposure layers] --> G[Composite Risk]
  F[Vulnerability layers] --> G
  D --> G
  G --> H[GeoTIFF, NetCDF, figures, tables]
```

## What this site includes

- Conceptual and quantitative methodology used by the pipeline
- Data lineage and licensing details for all core inputs
- Generated map outputs for drought and excess wetness risk
- Notebook-based inspection workflows
- Reproducibility instructions for local and CI builds

<style>
.hero {
  border-radius: 16px;
  padding: 24px 22px;
  margin: 0.25rem 0 1.2rem 0;
  background: linear-gradient(135deg, #0b2e4f 0%, #205b8f 52%, #4b9bc9 100%);
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(9, 30, 66, 0.18);
}
.hero-kicker {
  margin: 0;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
  font-size: 0.8rem;
  color: #cce7ff;
}
.hero-title {
  margin: 0.5rem 0 0.55rem 0;
  font-size: 1.8rem;
  line-height: 1.2;
  color: #ffffff;
}
.hero-subtitle {
  margin: 0;
  max-width: 860px;
  color: #e4f1fb;
}
.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 16px;
  margin: 1rem 0 1.25rem 0;
}
.tool-card {
  display: block;
  border: 1px solid #d2deea;
  border-radius: 12px;
  padding: 16px;
  text-decoration: none;
  background: linear-gradient(155deg, #f3f9ff 0%, #ffffff 100%);
  box-shadow: 0 3px 12px rgba(9, 30, 66, 0.08);
}
.tool-card:hover {
  border-color: #1e5d93;
  box-shadow: 0 8px 22px rgba(9, 30, 66, 0.15);
}
.tool-card h3 {
  margin-top: 0;
  margin-bottom: 0.4rem;
  color: #12395f;
}
.tool-card p {
  margin: 0;
  color: #2f4b67;
}
.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
  margin: 0.9rem 0 1.4rem 0;
}
.doc-pill {
  display: block;
  text-align: center;
  text-decoration: none;
  color: #11456f;
  border: 1px solid #bfd3e7;
  border-radius: 999px;
  padding: 8px 12px;
  background: #f7fbff;
  font-weight: 600;
}
.doc-pill:hover {
  background: #e9f4ff;
  border-color: #7fa8cc;
}
</style>
