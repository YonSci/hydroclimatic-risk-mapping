import numpy as np
import pytest
import xarray as xr

from hydroclim_risk.hazard.standardization import (
    cdd_dry_score,
    cwd_dry_score,
    cwd_wet_score,
    rainfall_percentile_dry_score,
    rainfall_percentile_wet_score,
    rx1day_wet_score,
    rx5day_wet_score,
    spi_dry_score,
    spi_wet_score,
)


def _da(values):
    return xr.DataArray(np.array(values, dtype="float64"), dims=("x",))


# --- SPI reference points from methodology.md ---


def test_spi_dry_score_reference_points():
    spi = _da([-2.0, -1.0, 0.0, 1.0])
    scores = spi_dry_score(spi).values
    np.testing.assert_allclose(scores, [1.00, 0.50, 0.00, 0.00])


def test_spi_wet_score_reference_points():
    spi = _da([1.0, 2.0, 0.0, -1.0])
    scores = spi_wet_score(spi).values
    np.testing.assert_allclose(scores, [0.50, 1.00, 0.00, 0.00])


def test_spi_score_saturates_beyond_extreme():
    spi = _da([-4.0, 4.0])
    np.testing.assert_allclose(spi_dry_score(spi).values, [1.0, 0.0])
    np.testing.assert_allclose(spi_wet_score(spi).values, [0.0, 1.0])


# --- Percentile-based scores (rainfall, CDD, CWD, Rx1day, Rx5day) ---


def test_rainfall_percentile_scores():
    p = _da([10, 50, 90])
    np.testing.assert_allclose(rainfall_percentile_dry_score(p).values, [1.0, 0.0, 0.0])
    np.testing.assert_allclose(rainfall_percentile_wet_score(p).values, [0.0, 0.0, 1.0])


def test_cdd_dry_score_high_percentile_is_dry():
    p = _da([10, 50, 90])
    np.testing.assert_allclose(cdd_dry_score(p).values, [0.0, 0.0, 1.0])


def test_cwd_scores_low_is_dry_high_is_wet():
    p = _da([10, 50, 90])
    np.testing.assert_allclose(cwd_dry_score(p).values, [1.0, 0.0, 0.0])
    np.testing.assert_allclose(cwd_wet_score(p).values, [0.0, 0.0, 1.0])


def test_rx1day_and_rx5day_wet_scores():
    p = _da([10, 50, 90])
    np.testing.assert_allclose(rx1day_wet_score(p).values, [0.0, 0.0, 1.0])
    np.testing.assert_allclose(rx5day_wet_score(p).values, [0.0, 0.0, 1.0])


def test_percentile_score_never_mixes_calendar_periods_is_caller_responsibility():
    # Not directly testable here (the function is period-agnostic by design) —
    # documents that callers must pass same-period percentile inputs, per
    # methodology.md "never mix calendar periods when computing a percentile rank".
    p = _da([50])
    assert rainfall_percentile_dry_score(p).values[0] == 0.0


# --- Dimension preservation (quality-safeguards.md: keep realization/year dim) ---


def test_scores_preserve_extra_dimensions():
    spi = xr.DataArray(
        np.array([[-2.0, -1.0], [0.0, 1.0]]),
        dims=("lat", "realization"),
        coords={"lat": [3.0, 3.25], "realization": [0, 1]},
    )
    scored = spi_dry_score(spi)
    assert scored.dims == ("lat", "realization")
    assert scored.shape == (2, 2)
    assert list(scored.coords["realization"].values) == [0, 1]
