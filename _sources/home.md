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

<div class="home-grid">
  <a class="home-card" href="docs/hazards.html">
    <h3>Hazards</h3>
    <p>Drought and excess-wetness hazard surfaces and interpretation.</p>
  </a>
  <a class="home-card" href="docs/exposure.html">
    <h3>Exposure</h3>
    <p>Sectoral exposure layers with notebook-based inspection references.</p>
  </a>
  <a class="home-card" href="docs/vulnerability.html">
    <h3>Vulnerability</h3>
    <p>Composite vulnerability structure and raw/derived input references.</p>
  </a>
  <a class="home-card" href="docs/methodology.html">
    <h3>Methodology</h3>
    <p>Formulas, standardization, weights, and hazard-probability logic.</p>
  </a>
  <a class="home-card" href="docs/data_provenance.html">
    <h3>Data Provenance</h3>
    <p>Source-by-source inventory with licenses, caveats, and exclusions.</p>
  </a>
  <a class="home-card" href="docs/results_gallery.html">
    <h3>Results Gallery</h3>
    <p>JJAS hazard, probability, severity, vulnerability, and risk maps.</p>
  </a>
  <a class="home-card" href="docs/reproducibility.html">
    <h3>Reproducibility</h3>
    <p>Environment setup, local docs build, and GitHub Pages publication.</p>
  </a>
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
.home-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
  margin: 1rem 0 1.25rem 0;
}
.home-card {
  display: block;
  border: 1px solid #d8e2eb;
  border-radius: 12px;
  padding: 14px;
  text-decoration: none;
  background: linear-gradient(160deg, #f8fbff 0%, #ffffff 100%);
  box-shadow: 0 2px 10px rgba(9, 30, 66, 0.06);
}
.home-card:hover {
  border-color: #3a6ea5;
  box-shadow: 0 6px 18px rgba(9, 30, 66, 0.12);
}
.home-card h3 {
  margin-top: 0;
  margin-bottom: 0.45rem;
  color: #0f355f;
}
.home-card p {
  margin: 0;
  color: #334e68;
}
</style>
