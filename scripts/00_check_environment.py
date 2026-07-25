"""Check that the hydroclimatic-risk environment is correctly installed."""

from __future__ import annotations

import importlib
import platform
import sys


PACKAGES = [
    "numpy",
    "pandas",
    "scipy",
    "xarray",
    "dask",
    "netCDF4",
    "h5netcdf",
    "zarr",
    "rasterio",
    "rioxarray",
    "geopandas",
    "shapely",
    "pyproj",
    "xclim",
    "matplotlib",
    "cartopy",
    "sklearn",
    "yaml",
]


def main() -> int:
    """Import required packages and print their versions."""
    print("=" * 70)
    print("HYDROCLIMATIC RISK ENVIRONMENT CHECK")
    print("=" * 70)
    print(f"Python executable : {sys.executable}")
    print(f"Python version    : {platform.python_version()}")
    print(f"Operating system : {platform.platform()}")
    print("-" * 70)

    failed: list[str] = []

    for package_name in PACKAGES:
        try:
            module = importlib.import_module(package_name)
            version = getattr(module, "__version__", "version not exposed")
            print(f"[OK]     {package_name:<15} {version}")
        except Exception as exc:
            failed.append(package_name)
            print(f"[FAILED] {package_name:<15} {exc}")

    print("-" * 70)

    if failed:
        print("Environment check failed.")
        print("Packages with errors:", ", ".join(failed))
        return 1

    print("All required packages imported successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())