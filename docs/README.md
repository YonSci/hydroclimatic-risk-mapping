# Documentation

- [methodology.md](methodology.md) -- the formulas this pipeline implements
  (hazard, probability, exposure, vulnerability, risk). Project-local
  snapshot of the skill's canonical reference
  (`.claude/skills/hydroclimatic-risk-mapping/references/methodology.md`).
- [data_provenance.md](data_provenance.md) -- every dataset used across the
  pipeline: source, license, citation, acquisition module, and what was
  deliberately excluded and why. Complements the per-file GeoTIFF tags
  (`rasterio.open(path).tags()`) with a single consolidated reference.

For the full architecture (module layout, config-driven design, grid
conventions), see `references/project-structure.md` and
`references/project-context.md` in the skill directory, and the module
docstrings under `src/hydroclim_risk/`.
