"""Spatial-alignment validation, per quality-safeguards.md: "verify all
input layers share grid, CRS, and time/season window before combining them;
fail loudly (not silently) on mismatch."
"""

from __future__ import annotations

from typing import Any

import numpy as np

from hydroclim_risk.config import load_data_config


class GridAlignmentError(ValueError):
    """Raised when arrays that are about to be combined don't share the same grid shape."""


def check_grid_alignment(
    arrays: dict[str, np.ndarray], domain_cfg: dict[str, Any] | None = None
) -> None:
    """Raise GridAlignmentError if any named array's shape doesn't match the
    analysis grid's (height, width) from config/data.yaml. Call this before
    combining arrays from different modules (e.g. risk/pipeline.py combining
    hazard/probability output with exposure/vulnerability output) -- a shape
    mismatch there would either crash confusingly deep in a broadcast or,
    worse, silently broadcast wrong if shapes happen to be compatible.
    """
    domain_cfg = domain_cfg or load_data_config()
    expected = tuple(domain_cfg["domain"]["grid_shape"])

    mismatched = {name: arr.shape for name, arr in arrays.items() if arr.shape != expected}
    if mismatched:
        raise GridAlignmentError(
            f"Grid shape mismatch (expected {expected}): "
            + ", ".join(f"{name}={shape}" for name, shape in mismatched.items())
        )
