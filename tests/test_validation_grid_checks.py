import numpy as np
import pytest

from hydroclim_risk.config import load_data_config
from hydroclim_risk.validation.grid_checks import GridAlignmentError, check_grid_alignment

CFG = load_data_config()
SHAPE = tuple(CFG["domain"]["grid_shape"])


def test_check_grid_alignment_passes_for_matching_shapes():
    arrays = {"a": np.zeros(SHAPE), "b": np.ones(SHAPE)}
    check_grid_alignment(arrays, CFG)  # should not raise


def test_check_grid_alignment_raises_with_offending_names_in_message():
    bad_shape = (SHAPE[0] + 1, SHAPE[1])
    arrays = {"good": np.zeros(SHAPE), "bad": np.zeros(bad_shape)}
    with pytest.raises(GridAlignmentError, match="bad"):
        check_grid_alignment(arrays, CFG)


def test_check_grid_alignment_all_bad_lists_all_names():
    arrays = {"x": np.zeros((1, 1)), "y": np.zeros((2, 2))}
    with pytest.raises(GridAlignmentError) as exc_info:
        check_grid_alignment(arrays, CFG)
    assert "x" in str(exc_info.value)
    assert "y" in str(exc_info.value)
