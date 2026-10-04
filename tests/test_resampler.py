"""
Tests for DataResampler.
All fixtures in this file are SYNTHETIC TEST DATA used solely for testing software behavior.
"""

import numpy as np
import pandas as pd
import pytest

from src.data.resampler import DataResampler


@pytest.fixture
def synthetic_15min_timeseries() -> pd.DataFrame:
    """
    SYNTHETIC TEST DATA FIXTURE
    Generates 24 hours of regular 15-minute synthetic data (96 observations).
    """
    dates = pd.date_range("2024-06-01 00:00:00", periods=96, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "dissolved_oxygen": 8.0 + 1.5 * np.sin(np.linspace(0, 2 * np.pi, 96)),
            "water_temperature": 18.0 + 3.0 * np.sin(np.linspace(0, 2 * np.pi, 96)),
            "discharge": [100.0] * 96,
        },
        index=dates,
    )
    return df


def test_detect_native_resolution_15min(synthetic_15min_timeseries):
    """Verifies correct detection of 15-minute native frequency."""
    info = DataResampler.detect_native_resolution(synthetic_15min_timeseries)
    assert info["native_frequency"] == "15-minute"
    assert info["median_interval_minutes"] == 15.0
    assert info["is_regular"] is True
    assert info["observation_count"] == 96


def test_resample_hourly(synthetic_15min_timeseries):
    """Verifies resampling from 15-min to 1-hour resolution (96 obs -> 24 obs)."""
    resampled = DataResampler.resample(synthetic_15min_timeseries, target_resolution="1h")
    assert len(resampled) == 24
    assert resampled.index.freqstr in ("1h", "h", "60min", "<Hour>")
    assert "dissolved_oxygen" in resampled.columns
    assert "discharge" in resampled.columns
    assert np.isclose(resampled["discharge"].mean(), 100.0)


def test_resample_daily(synthetic_15min_timeseries):
    """Verifies resampling to daily aggregation (96 obs -> 1 obs)."""
    resampled = DataResampler.resample(synthetic_15min_timeseries, target_resolution="1d")
    assert len(resampled) == 1


def test_resample_native_untouched(synthetic_15min_timeseries):
    """Verifies that 'native' resolution returns identical DataFrame."""
    resampled = DataResampler.resample(synthetic_15min_timeseries, target_resolution="native")
    pd.testing.assert_frame_equal(resampled, synthetic_15min_timeseries)
