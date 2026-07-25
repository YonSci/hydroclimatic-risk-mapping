import numpy as np
import pytest

from hydroclim_risk.config import load_thresholds_config
from hydroclim_risk.risk.risk import classify_risk, combine_dominant_risk, compute_risk, dominant_risk_code

THRESHOLDS = load_thresholds_config()


def _const(value, shape=(2, 2)):
    return np.full(shape, value, dtype="float64")


def test_compute_risk_matches_formula():
    p, s, e, v = _const(0.4), _const(0.5), _const(0.6), _const(0.3)
    result = compute_risk(p, s, e, v)
    np.testing.assert_allclose(result, 100.0 * 0.4 * 0.5 * 0.6 * 0.3)


def test_compute_risk_zero_any_factor_gives_zero_risk():
    p, s, e, v = _const(0.0), _const(0.5), _const(0.6), _const(0.3)
    result = compute_risk(p, s, e, v)
    np.testing.assert_allclose(result, 0.0)


def test_compute_risk_zero_probability_with_nan_severity_gives_zero_not_nan():
    # S is NaN by design wherever P=0 (probability.py) -- naive 0*NaN would
    # wrongly make R undefined at every zero-probability cell
    p = _const(0.0)
    s = _const(np.nan)
    e, v = _const(0.6), _const(0.3)
    result = compute_risk(p, s, e, v)
    np.testing.assert_allclose(result, 0.0)


def test_compute_risk_nan_probability_stays_nan():
    # genuinely missing/masked hazard data (P itself NaN, not 0) must NOT
    # be silently treated as zero risk
    p = _const(np.nan)
    s, e, v = _const(0.5), _const(0.6), _const(0.3)
    result = compute_risk(p, s, e, v)
    assert np.all(np.isnan(result))


def test_compute_risk_zero_probability_but_missing_exposure_stays_nan():
    # zero-probability hazard, but exposure data is itself missing at this
    # cell -- risk should stay unassessed (NaN), not silently reported as 0
    p = _const(0.0)
    s = _const(np.nan)
    e = _const(np.nan)
    v = _const(0.3)
    result = compute_risk(p, s, e, v)
    assert np.all(np.isnan(result))


def test_combine_dominant_risk_never_averages():
    r_drought = _const(20.0)
    r_wet = _const(80.0)
    result = combine_dominant_risk(r_drought, r_wet)
    np.testing.assert_allclose(result, 80.0)  # not 50 (the average)


@pytest.mark.parametrize(
    "r_drought,r_wet,expected_code",
    [
        (10.0, 5.0, THRESHOLDS["dominant_hazard_codes"]["none"]),       # both "Very low"
        (50.0, 10.0, THRESHOLDS["dominant_hazard_codes"]["drought"]),   # drought significant only
        (10.0, 50.0, THRESHOLDS["dominant_hazard_codes"]["wet"]),       # wet significant only
        (50.0, 60.0, THRESHOLDS["dominant_hazard_codes"]["mixed"]),     # both significant
    ],
)
def test_dominant_risk_code_branches(r_drought, r_wet, expected_code):
    code = dominant_risk_code(_const(r_drought), _const(r_wet))
    assert code[0, 0] == expected_code


def test_dominant_risk_code_propagates_nan():
    r_drought = np.array([50.0, np.nan, 10.0])
    r_wet = np.array([10.0, 50.0, np.nan])
    code = dominant_risk_code(r_drought, r_wet)
    assert code[0] == THRESHOLDS["dominant_hazard_codes"]["drought"]
    assert np.isnan(code[1])
    assert np.isnan(code[2])


def test_dominant_risk_code_default_threshold_is_very_low_ceiling():
    very_low_max = next(c for c in THRESHOLDS["risk_classes"] if c["label"] == "Very low")["max"]
    # exactly at the ceiling -> still "Very low" -> insignificant
    code_at = dominant_risk_code(_const(very_low_max), _const(0.0))
    assert code_at[0, 0] == THRESHOLDS["dominant_hazard_codes"]["none"]
    # just above -> significant
    code_above = dominant_risk_code(_const(very_low_max + 0.2), _const(0.0))
    assert code_above[0, 0] == THRESHOLDS["dominant_hazard_codes"]["drought"]


@pytest.mark.parametrize(
    "value,expected_label",
    [(0.0, "Very low"), (19.9, "Very low"), (20.0, "Low"), (39.9, "Low"),
     (40.0, "Moderate"), (59.9, "Moderate"), (60.0, "High"), (79.9, "High"),
     (80.0, "Very high"), (100.0, "Very high")],
)
def test_classify_risk_matches_configured_bands(value, expected_label):
    expected_code = next(c for c in THRESHOLDS["risk_classes"] if c["label"] == expected_label)["code"]
    result = classify_risk(_const(value))
    assert result[0, 0] == expected_code


def test_classify_risk_nan_stays_nan():
    r = np.array([50.0, np.nan])
    result = classify_risk(r)
    assert not np.isnan(result[0])
    assert np.isnan(result[1])
