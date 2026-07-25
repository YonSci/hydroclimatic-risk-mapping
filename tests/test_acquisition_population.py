from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from affine import Affine

from hydroclim_risk.acquisition.population import _latest_worldpop_file_url, download_population
from hydroclim_risk.config import load_data_config, load_yaml

CFG = load_data_config()
DOMAIN = CFG["domain"]
REAL_EXPOSURE_CFG = load_yaml("exposure_data")


def _cfg_with_tmp_dirs(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in REAL_EXPOSURE_CFG.items()}
    cfg["output_dir"] = str(tmp_path / "outputs")
    cfg["raw_cache_dir"] = str(tmp_path / "raw")
    return cfg


def _mock_api_response(entries):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"data": entries})
    return resp


def test_latest_worldpop_file_url_picks_max_year():
    entries = [
        {"popyear": "2015", "files": ["https://example.invalid/eth_2015.tif"]},
        {"popyear": "2020", "files": ["https://example.invalid/eth_2020.tif"]},
        {"popyear": "2018", "files": ["https://example.invalid/eth_2018.tif"]},
    ]
    with patch("hydroclim_risk.acquisition.population.requests.get", return_value=_mock_api_response(entries)):
        url, year = _latest_worldpop_file_url("https://example.invalid/api")
    assert year == "2020"
    assert url == "https://example.invalid/eth_2020.tif"


def test_latest_worldpop_file_url_raises_on_empty_data():
    with patch("hydroclim_risk.acquisition.population.requests.get", return_value=_mock_api_response([])):
        with pytest.raises(Exception, match="no datasets"):
            _latest_worldpop_file_url("https://example.invalid/api")


def _write_synthetic_worldpop_tif(path: Path):
    # a fine-resolution count raster exactly covering the analysis domain,
    # 10 people per source pixel everywhere, plus a nodata sentinel
    src_res = DOMAIN["resolution_deg"] / 4
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / src_res))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / src_res))
    transform = Affine(src_res, 0, DOMAIN["lon_min"], 0, -src_res, DOMAIN["lat_max"])
    data = np.full((n_lat, n_lon), 10.0, dtype="float32")
    data[0, 0] = -99999.0  # nodata sentinel, like real WorldPop edge pixels

    with rasterio.open(
        path, "w", driver="GTiff", height=n_lat, width=n_lon, count=1,
        dtype="float32", crs=DOMAIN["crs"], transform=transform, nodata=-99999.0,
    ) as dst:
        dst.write(data, 1)


def test_download_population_conserves_total_and_writes_tags(tmp_path: Path):
    exposure_cfg = _cfg_with_tmp_dirs(tmp_path)
    entries = [{"popyear": "2020", "files": ["https://example.invalid/eth_ppp_2020.tif"]}]

    def fake_download_file(url, dest_path, overwrite=False, timeout=120):
        _write_synthetic_worldpop_tif(Path(dest_path))
        return Path(dest_path)

    with patch("hydroclim_risk.acquisition.population.requests.get", return_value=_mock_api_response(entries)), \
         patch("hydroclim_risk.acquisition.population.download_file", side_effect=fake_download_file):
        dest = download_population(exposure_cfg=exposure_cfg)

    assert dest.exists()
    with rasterio.open(dest) as src:
        result = src.read(1)
        tags = src.tags()
    assert tags["popyear"] == "2020"
    assert tags["source"] == "worldpop"
    assert tags["variable"] == "population_count"
    # total should be close to 10 * (num source pixels, minus the 1 nodata pixel)
    n_lat = int(round((DOMAIN["lat_max"] - DOMAIN["lat_min"]) / (DOMAIN["resolution_deg"] / 4)))
    n_lon = int(round((DOMAIN["lon_max"] - DOMAIN["lon_min"]) / (DOMAIN["resolution_deg"] / 4)))
    expected_total = 10.0 * (n_lat * n_lon - 1)
    assert np.nansum(result) == pytest.approx(expected_total, rel=1e-2)
