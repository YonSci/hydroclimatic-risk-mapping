from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from typer.testing import CliRunner

from hydroclim_risk.cli import app
from hydroclim_risk.config import load_data_config

runner = CliRunner()
CFG = load_data_config()
DOMAIN = CFG["domain"]


def test_check_env_succeeds_with_real_environment():
    result = runner.invoke(app, ["check-env"])
    assert result.exit_code == 0
    assert "All required packages imported successfully" in result.stdout


def test_download_data_rejects_unknown_dataset_name():
    result = runner.invoke(app, ["download-data", "--only", "not_a_real_dataset"])
    assert result.exit_code != 0


def test_generate_risk_rejects_unknown_period():
    result = runner.invoke(app, ["generate-risk", "--periods", "NotAMonth"])
    assert result.exit_code != 0


def test_generate_risk_rejects_unknown_sector():
    result = runner.invoke(app, ["generate-risk", "--sectors", "not_a_real_sector"])
    assert result.exit_code != 0


def _write_tif(path: Path, arr: np.ndarray):
    transform = Affine(DOMAIN["resolution_deg"], 0, DOMAIN["lon_min"], 0, -DOMAIN["resolution_deg"], DOMAIN["lat_max"])
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform,
    ) as dst:
        dst.write(arr, 1)


def test_validate_clean_directory_exits_zero(tmp_path: Path):
    _write_tif(tmp_path / "ok.tif", np.array([[1.0, 2.0], [3.0, 4.0]]))
    result = runner.invoke(app, ["validate", "--directory", str(tmp_path)])
    assert result.exit_code == 0
    assert "No Inf/constant issues found" in result.stdout


def test_validate_flags_constant_file_and_exits_nonzero(tmp_path: Path):
    _write_tif(tmp_path / "const.tif", np.full((2, 2), 5.0))
    result = runner.invoke(app, ["validate", "--directory", str(tmp_path)])
    assert result.exit_code != 0
    assert "const.tif" in result.stdout


def test_validate_empty_directory_does_not_crash(tmp_path: Path):
    result = runner.invoke(app, ["validate", "--directory", str(tmp_path)])
    assert result.exit_code == 0
    assert "Scanned 0 file" in result.stdout
