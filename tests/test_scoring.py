import numpy as np
import pytest

from hydroclim_risk.scoring import weighted_sum


class MyError(ValueError):
    pass


def test_weighted_sum_basic():
    scores = {"a": np.array([1.0, 2.0]), "b": np.array([10.0, 20.0])}
    weights = {"a": 0.3, "b": 0.7}
    result = weighted_sum(scores, weights, "group", MyError)
    expected = 0.3 * np.array([1.0, 2.0]) + 0.7 * np.array([10.0, 20.0])
    np.testing.assert_allclose(result, expected)


def test_weighted_sum_raises_on_missing_key():
    scores = {"a": np.array([1.0])}
    weights = {"a": 0.5, "b": 0.5}
    with pytest.raises(MyError, match="missing"):
        weighted_sum(scores, weights, "group", MyError)


def test_weighted_sum_raises_on_extra_key():
    scores = {"a": np.array([1.0]), "b": np.array([1.0]), "c": np.array([1.0])}
    weights = {"a": 0.5, "b": 0.5}
    with pytest.raises(MyError, match="unexpected"):
        weighted_sum(scores, weights, "group", MyError)


def test_weighted_sum_uses_custom_error_class():
    with pytest.raises(MyError):
        weighted_sum({}, {"x": 1.0}, "group", MyError)
