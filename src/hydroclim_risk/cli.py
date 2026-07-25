"""Command-line interface for the hydroclim_risk pipeline.

    python -m hydroclim_risk.cli check-env
    python -m hydroclim_risk.cli download-data [--only population,livestock]
    python -m hydroclim_risk.cli generate-risk [--periods June,JJAS] [--sectors population]
    python -m hydroclim_risk.cli validate [--directory outputs/risk]

Each subcommand is a thin wrapper around the same functions used by
scripts/00_check_environment.py, scripts/02_download_exposure_vulnerability_
data.py, and scripts/03_generate_risk_maps.py -- no business logic lives
here, only argument parsing and orchestration.
"""

from __future__ import annotations

import importlib
import platform
import sys
from typing import Optional

import typer

app = typer.Typer(help="Ethiopia hydroclimatic risk-mapping pipeline CLI.", no_args_is_help=True)

_ENV_PACKAGES = [
    "numpy", "pandas", "scipy", "xarray", "dask", "netCDF4", "h5netcdf", "zarr",
    "rasterio", "rioxarray", "geopandas", "shapely", "pyproj", "xclim",
    "matplotlib", "cartopy", "sklearn", "yaml",
]

_ALL_DATASETS = [
    "population", "cropland", "livestock", "poverty", "irrigation",
    "ghs_built", "healthsites", "infrastructure", "aridity", "gdessa",
    "terrain", "soil_drainage", "river_proximity",
]

_ALL_PERIODS = ["June", "July", "August", "September", "JJAS"]


@app.command("check-env")
def check_env() -> None:
    """Verify the Python environment has every required package installed."""
    print("=" * 70)
    print("HYDROCLIMATIC RISK ENVIRONMENT CHECK")
    print("=" * 70)
    print(f"Python executable : {sys.executable}")
    print(f"Python version    : {platform.python_version()}")
    print("-" * 70)

    failed: list[str] = []
    for name in _ENV_PACKAGES:
        try:
            module = importlib.import_module(name)
            version = getattr(module, "__version__", "version not exposed")
            print(f"[OK]     {name:<15} {version}")
        except Exception as exc:
            failed.append(name)
            print(f"[FAILED] {name:<15} {exc}")

    print("-" * 70)
    if failed:
        print("Environment check failed. Packages with errors:", ", ".join(failed))
        raise typer.Exit(code=1)
    print("All required packages imported successfully.")


@app.command("download-data")
def download_data(
    only: Optional[str] = typer.Option(
        None, help=f"Comma-separated subset of {_ALL_DATASETS} (default: all)."
    ),
) -> None:
    """Download and resample all exposure/vulnerability datasets."""
    from hydroclim_risk.acquisition.aridity import download_aridity
    from hydroclim_risk.acquisition.cropland import download_cropland
    from hydroclim_risk.acquisition.gdessa import download_gdessa
    from hydroclim_risk.acquisition.ghs_built import download_ghs_built
    from hydroclim_risk.acquisition.healthsites import download_healthsites
    from hydroclim_risk.acquisition.infrastructure import download_buildings, download_roads
    from hydroclim_risk.acquisition.irrigation import download_irrigation
    from hydroclim_risk.acquisition.livestock import download_livestock
    from hydroclim_risk.acquisition.population import download_population
    from hydroclim_risk.acquisition.poverty import download_poverty
    from hydroclim_risk.acquisition.river_proximity import download_river_proximity
    from hydroclim_risk.acquisition.soil_drainage import download_soil_drainage
    from hydroclim_risk.acquisition.terrain import download_terrain
    from hydroclim_risk.config import load_yaml

    def run_livestock() -> None:
        exposure_cfg = load_yaml("exposure_data")
        for species in exposure_cfg["datasets"]["livestock"]["species"]:
            print(f"    {species} -> {download_livestock(species)}")

    def run_infrastructure() -> None:
        print(f"    roads -> {download_roads()}")
        print(f"    buildings -> {download_buildings()}")

    def run_terrain() -> None:
        elevation, slope = download_terrain()
        print(f"    elevation -> {elevation}")
        print(f"    slope -> {slope}")

    runners = {
        "population": lambda: print(f"    -> {download_population()}"),
        "cropland": lambda: print(f"    -> {download_cropland()}"),
        "livestock": run_livestock,
        "poverty": lambda: print(f"    -> {download_poverty()}"),
        "irrigation": lambda: print(f"    -> {download_irrigation()}"),
        "ghs_built": lambda: print(f"    -> {download_ghs_built()}"),
        "healthsites": lambda: print(f"    -> {download_healthsites()}"),
        "infrastructure": run_infrastructure,
        "aridity": lambda: print(f"    -> {download_aridity()}"),
        "gdessa": lambda: print(f"    -> {download_gdessa()}"),
        "terrain": run_terrain,
        "soil_drainage": lambda: print(f"    -> {download_soil_drainage()}"),
        "river_proximity": lambda: print(f"    -> {download_river_proximity()}"),
    }

    selected = only.split(",") if only else list(runners)
    unknown = set(selected) - set(runners)
    if unknown:
        typer.echo(f"Unknown dataset(s): {sorted(unknown)}. Choose from {list(runners)}.", err=True)
        raise typer.Exit(code=1)

    failed: list[str] = []
    for name in selected:
        print(f"\n--- {name} ---")
        try:
            runners[name]()
        except Exception as exc:
            print(f"[FAILED] {name}: {exc}")
            failed.append(name)

    if failed:
        typer.echo(f"Failed: {', '.join(failed)}", err=True)
        raise typer.Exit(code=1)
    print("\nAll datasets downloaded and resampled successfully.")


@app.command("generate-risk")
def generate_risk(
    periods: Optional[str] = typer.Option(None, help=f"Comma-separated subset of {_ALL_PERIODS} (default: all)."),
    sectors: Optional[str] = typer.Option(
        None, help="Comma-separated exposure sectors (default: all in config/exposure_indicators.yaml)."
    ),
) -> None:
    """Compute and write R_drought/R_wet/R_dominant/risk_class for every
    forecast period x exposure sector to outputs/risk/.
    """
    from hydroclim_risk.config import load_data_config, load_yaml
    from hydroclim_risk.exposure import compute_exposure_layer
    from hydroclim_risk.risk.pipeline import compute_hazard_and_probability_for_period, write_risk_layers
    from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code
    from hydroclim_risk.vulnerability import compute_v_drought, compute_v_wet

    domain_cfg = load_data_config()
    exp_ind_cfg = load_yaml("exposure_indicators")
    all_sectors = list(exp_ind_cfg["layers"])

    selected_periods = periods.split(",") if periods else _ALL_PERIODS
    selected_sectors = sectors.split(",") if sectors else all_sectors

    unknown_periods = set(selected_periods) - set(_ALL_PERIODS)
    unknown_sectors = set(selected_sectors) - set(all_sectors)
    if unknown_periods:
        typer.echo(f"Unknown period(s): {sorted(unknown_periods)}. Choose from {_ALL_PERIODS}.", err=True)
        raise typer.Exit(code=1)
    if unknown_sectors:
        typer.echo(f"Unknown sector(s): {sorted(unknown_sectors)}. Choose from {all_sectors}.", err=True)
        raise typer.Exit(code=1)

    print("Computing vulnerability (static, shared across every period/sector)...")
    v_drought = compute_v_drought(domain_cfg=domain_cfg)
    v_wet = compute_v_wet(domain_cfg=domain_cfg)

    failed: list[str] = []
    n_written = 0
    for period in selected_periods:
        print(f"\n--- {period} ---")
        try:
            hazard_prob = compute_hazard_and_probability_for_period(period)
        except Exception as exc:
            print(f"[FAILED] {period} hazard/probability: {exc}")
            failed.append(f"{period} (hazard/probability)")
            continue

        for sector in selected_sectors:
            key = f"{period}/{sector}"
            try:
                e_layer = compute_exposure_layer(sector, domain_cfg=domain_cfg)
                r_drought = compute_risk(hazard_prob["p_drought"], hazard_prob["s_drought"], e_layer.normalized, v_drought)
                r_wet = compute_risk(hazard_prob["p_wet"], hazard_prob["s_wet"], e_layer.normalized, v_wet)
                r_dominant = combine_dominant_risk(r_drought, r_wet)
                risk_result = {
                    "r_drought": r_drought,
                    "r_wet": r_wet,
                    "r_dominant": r_dominant,
                    "dominant_code": dominant_risk_code(r_drought, r_wet),
                    "risk_class": classify_risk(r_dominant),
                }
                written = write_risk_layers(period, sector, risk_result, domain_cfg=domain_cfg)
                n_written += len(written)
                print(f"  [OK] {key} -> {len(written)} files")
            except Exception as exc:
                print(f"  [FAILED] {key}: {exc}")
                failed.append(key)

    print(f"\nWrote {n_written} risk GeoTIFFs to outputs/risk/.")
    if failed:
        typer.echo(f"Failed: {', '.join(failed)}", err=True)
        raise typer.Exit(code=1)


@app.command("validate")
def validate(
    directory: str = typer.Option("outputs/risk", help="Directory of GeoTIFFs to QC (non-recursive)."),
    pattern: str = typer.Option("*.tif", help="Glob pattern for files to scan."),
) -> None:
    """Scan a directory of GeoTIFF outputs and flag Inf values or constant
    (zero-variance) files -- the two red flags found repeatedly during this
    project's real-data QC passes.
    """
    from hydroclim_risk.validation import generate_qc_report, validate_no_infs_or_constants

    report = generate_qc_report(directory, pattern=pattern)
    print(f"Scanned {len(report)} file(s) in {directory}")
    if report.empty:
        return

    flagged = validate_no_infs_or_constants(report)
    if not flagged.empty:
        print(f"\n{len(flagged)} file(s) flagged (Inf values or constant):")
        print(flagged[["file", "n_inf", "is_constant"]].to_string(index=False))
        raise typer.Exit(code=1)
    print("No Inf/constant issues found.")


if __name__ == "__main__":
    app()
