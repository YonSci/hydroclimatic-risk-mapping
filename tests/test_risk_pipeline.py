from pathlib import Path

import numpy as np
import rasterio

from hydroclim_risk.config import load_data_config
from hydroclim_risk.risk.pipeline import write_risk_layers

CFG = load_data_config()
DOMAIN = CFG["domain"]


def test_write_risk_layers_writes_all_products_with_correct_naming(tmp_path: Path):
    shape = tuple(DOMAIN["grid_shape"])
    risk_result = {
        "r_drought": np.full(shape, 5.0),
        "r_wet": np.full(shape, 2.0),
        "r_dominant": np.full(shape, 5.0),
        "dominant_code": np.full(shape, 1.0),
        "risk_class": np.full(shape, 0.0),
    }

    written = write_risk_layers(
        "June", "population", risk_result, domain_cfg=CFG, output_dir=tmp_path, init_date="2026-05-01"
    )

    assert set(written) == set(risk_result)
    for product, path in written.items():
        assert path.name == f"ethiopia_June_2026-05-01_population_{product}.tif"
        assert path.exists()
        with rasterio.open(path) as src:
            result = src.read(1)
            tags = src.tags()
        np.testing.assert_allclose(result, risk_result[product])
        assert tags["period"] == "June"
        assert tags["sector"] == "population"
        assert tags["product"] == product
