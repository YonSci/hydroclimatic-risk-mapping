"""Load and validate the project's YAML config files (config/*.yaml).

Every threshold, weight, path, and period name in the pipeline must come from
these files, never be hardcoded in a calculation module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigError(ValueError):
    """Raised when a config file is missing, malformed, or fails validation."""


def load_yaml(name: str, config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    """Load a single config/<name>.yaml file as a dict."""
    path = config_dir / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError(f"Config file did not parse to a mapping: {path}")
    return data


def load_data_config(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    return load_yaml("data", config_dir)


def load_periods_config(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    return load_yaml("periods", config_dir)


def load_thresholds_config(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    return load_yaml("thresholds", config_dir)


def load_standardization_config(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    return load_yaml("standardization", config_dir)


def load_weights_config(
    config_dir: Path = CONFIG_DIR, validate: bool = True
) -> dict[str, Any]:
    """Load weights.yaml; by default assert every weight group sums to 1.0.

    Fails loudly (ConfigError) rather than silently renormalizing, per
    quality-safeguards.md — a mismatched sum means the config was edited
    incorrectly and must be fixed at the source, not patched around.
    """
    cfg = load_yaml("weights", config_dir)
    if validate:
        validation = cfg.get("validation", {})
        tolerance = float(validation.get("sum_to_one_tolerance", 1e-6))
        groups = validation.get("groups_requiring_sum_to_one", [])
        for group in groups:
            weights = cfg.get(group)
            if not isinstance(weights, dict):
                raise ConfigError(f"weights.yaml: missing weight group '{group}'")
            total = sum(weights.values())
            if abs(total - 1.0) > tolerance:
                raise ConfigError(
                    f"weights.yaml: group '{group}' weights sum to {total!r}, "
                    f"expected 1.0 (+/-{tolerance})"
                )
    return cfg
