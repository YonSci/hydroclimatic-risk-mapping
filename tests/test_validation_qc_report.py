from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from hydroclim_risk.config import load_data_config
from hydroclim_risk.validation.qc_report import generate_qc_report, validate_bounds, validate_no_infs_or_constants

CFG = load_data_config()
DOMAIN = CFG["domain"]


def _write_tif(path: Path, arr: np.ndarray, nodata=None):
    transform = Affine(DOMAIN["resolution_deg"], 0, DOMAIN["lon_min"], 0, -DOMAIN["resolution_deg"], DOMAIN["lat_max"])
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
        dtype="float64", crs=DOMAIN["crs"], transform=transform, nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def test_generate_qc_report_computes_correct_stats(tmp_path: Path):
    arr = np.array([[1.0, 2.0, np.nan], [3.0, 4.0, 5.0]])
    _write_tif(tmp_path / "a.tif", arr)

    report = generate_qc_report(tmp_path)
    assert len(report) == 1
    row = report.iloc[0]
    assert row["file"] == "a.tif"
    assert row["n_total"] == 6
    assert row["n_valid"] == 5
    assert row["pct_valid"] == 5 / 6
    assert row["min"] == 1.0
    assert row["max"] == 5.0
    assert row["mean"] == 3.0
    assert row["is_constant"] == False  # noqa: E712


def test_generate_qc_report_detects_constant_array(tmp_path: Path):
    _write_tif(tmp_path / "const.tif", np.full((3, 3), 7.0))
    report = generate_qc_report(tmp_path)
    assert report.iloc[0]["is_constant"] == True  # noqa: E712


def test_generate_qc_report_detects_infs(tmp_path: Path):
    arr = np.array([[1.0, np.inf], [2.0, 3.0]])
    _write_tif(tmp_path / "hasinf.tif", arr)
    report = generate_qc_report(tmp_path)
    assert report.iloc[0]["n_inf"] == 1


def test_generate_qc_report_scans_multiple_files_sorted(tmp_path: Path):
    _write_tif(tmp_path / "b.tif", np.full((2, 2), 1.0))
    _write_tif(tmp_path / "a.tif", np.full((2, 2), 2.0))
    report = generate_qc_report(tmp_path)
    assert list(report["file"]) == ["a.tif", "b.tif"]


def test_generate_qc_report_pattern_filters_files(tmp_path: Path):
    _write_tif(tmp_path / "keep.tif", np.full((2, 2), 1.0))
    (tmp_path / "ignore.txt").write_text("not a tif")
    report = generate_qc_report(tmp_path)
    assert len(report) == 1
    assert report.iloc[0]["file"] == "keep.tif"


def test_validate_bounds_flags_out_of_range_files(tmp_path: Path):
    _write_tif(tmp_path / "ok.tif", np.full((2, 2), 50.0))
    _write_tif(tmp_path / "toohigh.tif", np.full((2, 2), 150.0))
    _write_tif(tmp_path / "toolow.tif", np.full((2, 2), -10.0))

    report = generate_qc_report(tmp_path)
    violations = validate_bounds(report, min_value=0, max_value=100)

    assert set(violations["file"]) == {"toohigh.tif", "toolow.tif"}


def test_validate_bounds_empty_report_returns_empty(tmp_path: Path):
    report = generate_qc_report(tmp_path)  # empty dir -> empty report
    violations = validate_bounds(report, min_value=0, max_value=100)
    assert violations.empty


def test_validate_no_infs_or_constants_flags_both(tmp_path: Path):
    _write_tif(tmp_path / "normal.tif", np.array([[1.0, 2.0], [3.0, 4.0]]))
    _write_tif(tmp_path / "const.tif", np.full((2, 2), 5.0))
    _write_tif(tmp_path / "hasinf.tif", np.array([[1.0, np.inf], [2.0, 3.0]]))

    report = generate_qc_report(tmp_path)
    flagged = validate_no_infs_or_constants(report)

    assert set(flagged["file"]) == {"const.tif", "hasinf.tif"}
