from pathlib import Path

import pytest
import yaml

from hydroclim_risk.config import ConfigError, load_weights_config, load_yaml


def test_load_yaml_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_yaml("does_not_exist", config_dir=tmp_path)


def test_real_weights_config_sums_to_one():
    cfg = load_weights_config()
    for group in cfg["validation"]["groups_requiring_sum_to_one"]:
        assert abs(sum(cfg[group].values()) - 1.0) < 1e-9


def test_load_weights_config_rejects_bad_sum(tmp_path: Path):
    bad_weights = {
        "h_dry": {"a": 0.5, "b": 0.4},  # sums to 0.9, not 1.0
        "validation": {
            "sum_to_one_tolerance": 1e-6,
            "groups_requiring_sum_to_one": ["h_dry"],
        },
    }
    (tmp_path / "weights.yaml").write_text(yaml.safe_dump(bad_weights))

    with pytest.raises(ConfigError, match="sum to"):
        load_weights_config(config_dir=tmp_path)
