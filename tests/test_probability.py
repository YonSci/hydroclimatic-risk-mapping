import warnings

import numpy as np
import pytest
import xarray as xr

from hydroclim_risk.probability.probability import (
    compute_p_any,
    compute_p_drought,
    compute_p_wet,
    compute_s_drought,
    compute_s_wet,
)

THRESHOLD = 0.60


def _da(values):
    """1D 'realization' DataArray, wrapped in an extra 'x' dim of size 1 so
    results come back with a grid-like shape (matches real usage)."""
    return xr.DataArray(np.array([values], dtype="float64"), dims=("x", "realization"))


# --- P_drought / P_wet ---


def test_compute_p_drought_basic_fraction():
    h_dry = _da([0.7, 0.7, 0.3, 0.3, 0.7])  # 3 of 5 exceed 0.60
    p = compute_p_drought(h_dry, threshold=THRESHOLD)
    np.testing.assert_allclose(p.values, [0.6])


def test_compute_p_drought_all_exceed():
    h_dry = _da([0.9] * 5)
    p = compute_p_drought(h_dry, threshold=THRESHOLD)
    np.testing.assert_allclose(p.values, [1.0])


def test_compute_p_drought_none_exceed():
    h_dry = _da([0.1] * 5)
    p = compute_p_drought(h_dry, threshold=THRESHOLD)
    np.testing.assert_allclose(p.values, [0.0])


def test_compute_p_drought_all_nan_gives_nan_not_zero():
    h_dry = _da([np.nan] * 5)
    p = compute_p_drought(h_dry, threshold=THRESHOLD)
    assert np.isnan(p.values[0])


def test_compute_p_drought_collapses_realization_dim():
    h_dry = _da([0.7, 0.3, 0.3, 0.3, 0.3])
    p = compute_p_drought(h_dry, threshold=THRESHOLD)
    assert "realization" not in p.dims
    assert p.dims == ("x",)


# --- P_any (OR logic) ---


def test_compute_p_any_or_logic_matches_hand_count():
    # exceed(dry) = [T,T,F,F,T] (3), exceed(wet) = [F,T,F,T,T] (3), OR = [T,T,F,T,T] (4)
    h_dry = _da([0.7, 0.7, 0.3, 0.3, 0.7])
    h_wet = _da([0.2, 0.7, 0.2, 0.7, 0.7])

    assert compute_p_drought(h_dry, threshold=THRESHOLD).values[0] == pytest.approx(0.6)
    assert compute_p_wet(h_wet, threshold=THRESHOLD).values[0] == pytest.approx(0.6)

    p_any = compute_p_any(h_dry, h_wet, threshold=THRESHOLD)
    np.testing.assert_allclose(p_any.values, [0.8])


def test_compute_p_any_nan_where_either_input_nan():
    h_dry = _da([0.7, np.nan, 0.3])
    h_wet = _da([0.2, 0.8, np.nan])
    # this tiny 3-member example is itself a partial ensemble (1 of 3 valid) —
    # expect (and ignore) the sample-size warning, that's not what's under test here
    with pytest.warns(UserWarning, match="partial ensemble"):
        p_any = compute_p_any(h_dry, h_wet, threshold=THRESHOLD)
    # only realization index 0 has both inputs valid
    assert p_any.values[0] == pytest.approx(1.0)  # 1 of 1 valid member exceeds (dry side)


# --- Conditional severity S_drought / S_wet ---


def test_compute_s_drought_mean_of_qualifying_members_only():
    h_dry = _da([0.7, 0.9, 0.3, 0.3, 0.65])  # qualifying (>=0.6): 0.7, 0.9, 0.65
    s = compute_s_drought(h_dry, threshold=THRESHOLD)
    expected = (0.7 + 0.9 + 0.65) / 3
    np.testing.assert_allclose(s.values, [expected])


def test_compute_s_drought_nan_when_no_member_qualifies():
    h_dry = _da([0.1, 0.2, 0.3])  # none exceed threshold
    s = compute_s_drought(h_dry, threshold=THRESHOLD)
    assert np.isnan(s.values[0])  # NaN, not 0 — "no event" != "zero severity"


def test_compute_s_wet_mean_of_qualifying_members_only():
    h_wet = _da([0.65, 0.75, 0.1, 0.1])
    s = compute_s_wet(h_wet, threshold=THRESHOLD)
    expected = (0.65 + 0.75) / 2
    np.testing.assert_allclose(s.values, [expected])


# --- Sample-size safeguard (quality-safeguards.md) ---


def test_partial_ensemble_triggers_warning():
    values = [0.7] * 10 + [np.nan] * 15  # 10 of 25 valid — partial ensemble
    h_dry = _da(values)
    with pytest.warns(UserWarning, match="partial ensemble"):
        compute_p_drought(h_dry, threshold=THRESHOLD)


def test_full_ensemble_does_not_warn():
    h_dry = _da([0.7] * 25)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compute_p_drought(h_dry, threshold=THRESHOLD)
