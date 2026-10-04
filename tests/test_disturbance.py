"""
Tests for DisturbanceDetector and candidate hydrologic disturbance event detection.
All fixtures in this file are SYNTHETIC TEST DATA used solely for testing software behavior.
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.disturbance import DisturbanceDetector


@pytest.fixture
def synthetic_storm_discharge_series() -> pd.DataFrame:
    """
    SYNTHETIC TEST DATA FIXTURE
    Constructs a 14-day 15-minute time series (1344 observations) with a synthetic
    discharge surge on day 7:
    - Baseline discharge: ~100 cfs
    - Storm peak: 550 cfs (5.5x baseline)
    - Concomitant DO depression from 8.5 mg/L down to 5.2 mg/L
    - Turbidity spike from 4 FNU to 85 FNU
    """
    dates = pd.date_range("2024-06-01", periods=1344, freq="15min", tz="UTC")

    # Base arrays
    q = np.full(len(dates), 100.0)
    do = np.full(len(dates), 8.5)
    temp = np.full(len(dates), 20.0)
    turb = np.full(len(dates), 4.0)

    # Inject storm hydrograph between index 600 and 750 (approx Day 7)
    storm_idx = np.arange(600, 750)
    peak_offset = 50
    # Triangular surge
    surge = np.zeros(len(storm_idx))
    surge[:peak_offset] = np.linspace(0, 450, peak_offset)
    surge[peak_offset:] = np.linspace(450, 0, len(storm_idx) - peak_offset)

    q[storm_idx] += surge
    # DO depression following peak
    do[storm_idx] -= (surge / 450.0) * 3.3
    turb[storm_idx] += (surge / 450.0) * 81.0

    df = pd.DataFrame(
        {
            "discharge": q,
            "dissolved_oxygen": do,
            "water_temperature": temp,
            "turbidity": turb,
        },
        index=dates,
    )
    return df


def test_detect_candidate_storm_events(synthetic_storm_discharge_series):
    """
    Verifies that the synthetic discharge surge is correctly identified as a
    candidate hydrologic disturbance event, and that DO drop and turbidity response
    are calculated accurately.
    """
    detector = DisturbanceDetector()
    events_df = detector.detect_candidate_events(
        synthetic_storm_discharge_series,
        station_id="SYNTHETIC_TEST_01",
        save_csv=False,
    )

    assert not events_df.empty
    assert len(events_df) == 1

    event = events_df.iloc[0]
    assert event["station_id"] == "SYNTHETIC_TEST_01"
    # Peak discharge should be ~550 cfs
    assert np.isclose(event["peak_discharge_cfs"], 550.0, atol=1.0)
    # Baseline discharge should be ~100 cfs
    assert np.isclose(event["baseline_discharge_cfs"], 100.0, atol=5.0)
    # Spike ratio should be ~5.5
    assert np.isclose(event["discharge_spike_ratio"], 5.5, atol=0.2)
    # Pre-event DO ~ 8.5 mg/L
    assert np.isclose(event["pre_event_do_mg_L"], 8.5, atol=0.2)
    # Min DO after event ~ 5.2 mg/L
    assert np.isclose(event["min_do_after_event_mg_L"], 5.2, atol=0.2)
    # DO drop ~ 3.3 mg/L
    assert np.isclose(event["do_drop_mg_L"], 3.3, atol=0.3)
    # Turbidity peak response ~ 85.0
    assert np.isclose(event["turbidity_peak_response"], 85.0, atol=2.0)
