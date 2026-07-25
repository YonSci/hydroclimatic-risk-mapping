import numpy as np
import pytest
import xarray as xr

from hydroclim_risk.config import load_thresholds_config, load_weights_config
from hydroclim_risk.hazard.hazard import (
    HazardError,
    combine_hazard,
    compute_h_dry,
    compute_h_wet,
    dominant_hazard_code,
)

WEIGHTS = load_weights_config()
THRESHOLDS = load_thresholds_config()


def _const(value):
    return xr.DataArray(np.full((2, 2), value, dtype="float64"), dims=("lat", "lon"))


def test_compute_h_dry_all_ones_sums_to_one():
    scores = {key: _const(1.0) for key in WEIGHTS["h_dry"]}
    h_dry = compute_h_dry(scores)
    np.testing.assert_allclose(h_dry.values, 1.0)


def test_compute_h_dry_matches_manual_weighted_sum():
    scores = {
        "spi_dry_score": _const(1.0),
        "rainfall_percentile_dry_score": _const(0.5),
        "cdd_dry_score": _const(0.0),
        "cwd_dry_score": _const(0.2),
    }
    expected = 0.35 * 1.0 + 0.20 * 0.5 + 0.30 * 0.0 + 0.15 * 0.2
    h_dry = compute_h_dry(scores)
    np.testing.assert_allclose(h_dry.values, expected)


def test_compute_h_wet_all_ones_sums_to_one():
    scores = {key: _const(1.0) for key in WEIGHTS["h_wet"]}
    h_wet = compute_h_wet(scores)
    np.testing.assert_allclose(h_wet.values, 1.0)


def test_compute_h_dry_rejects_missing_key():
    scores = {key: _const(1.0) for key in WEIGHTS["h_dry"]}
    del scores["cwd_dry_score"]
    with pytest.raises(HazardError, match="missing"):
        compute_h_dry(scores)


def test_compute_h_dry_rejects_unexpected_key():
    scores = {key: _const(1.0) for key in WEIGHTS["h_dry"]}
    scores["rx5day_wet_score"] = _const(1.0)  # belongs to h_wet, not h_dry
    with pytest.raises(HazardError, match="unexpected"):
        compute_h_dry(scores)


def test_combine_hazard_never_averages():
    h_dry = _const(0.2)
    h_wet = _const(0.9)
    overall = combine_hazard(h_dry, h_wet)
    # if this ever averaged, we'd get 0.55 — must be the max, 0.9
    np.testing.assert_allclose(overall.values, 0.9)

    h_dry2 = _const(0.8)
    h_wet2 = _const(0.3)
    overall2 = combine_hazard(h_dry2, h_wet2)
    np.testing.assert_allclose(overall2.values, 0.8)


@pytest.mark.parametrize(
    "h_dry,h_wet,expected_code",
    [
        (0.30, 0.20, THRESHOLDS["dominant_hazard_codes"]["none"]),
        (0.70, 0.20, THRESHOLDS["dominant_hazard_codes"]["drought"]),
        (0.20, 0.70, THRESHOLDS["dominant_hazard_codes"]["wet"]),
        (0.70, 0.65, THRESHOLDS["dominant_hazard_codes"]["mixed"]),
    ],
)
def test_dominant_hazard_code_branches(h_dry, h_wet, expected_code):
    code = dominant_hazard_code(_const(h_dry), _const(h_wet))
    assert int(code.values[0, 0]) == expected_code


def test_dominant_hazard_code_propagates_nan_for_missing_data():
    # NaN >= threshold is False, not NaN — a naive xr.where chain would
    # mislabel no-data cells as "no hazard" (code 0) instead of missing.
    h_dry = xr.DataArray([0.7, np.nan, 0.3], dims=("x",))
    h_wet = xr.DataArray([0.2, 0.8, np.nan], dims=("x",))
    code = dominant_hazard_code(h_dry, h_wet)
    assert code.values[0] == THRESHOLDS["dominant_hazard_codes"]["drought"]
    assert np.isnan(code.values[1])
    assert np.isnan(code.values[2])


def test_dominant_hazard_code_preserves_dims():
    h_dry = xr.DataArray(
        np.array([[0.1, 0.7], [0.65, 0.9]]),
        dims=("lat", "lon"),
        coords={"lat": [3.0, 3.25], "lon": [33.0, 33.25]},
    )
    h_wet = xr.DataArray(
        np.array([[0.2, 0.2], [0.7, 0.1]]),
        dims=("lat", "lon"),
        coords={"lat": [3.0, 3.25], "lon": [33.0, 33.25]},
    )
    code = dominant_hazard_code(h_dry, h_wet)
    assert code.dims == ("lat", "lon")
    assert code.shape == (2, 2)
