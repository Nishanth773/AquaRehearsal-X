"""
Tests for DataQualityAnalyzer and StationEvaluator.
All fixtures in this file are SYNTHETIC TEST DATA used solely for testing software behavior.
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.quality import DataQualityAnalyzer
from src.data.discovery import StationEvaluator


@pytest.fixture
def synthetic_complete_station_data() -> tuple:
    """
    SYNTHETIC TEST DATA FIXTURE
    Generates a regular 15-minute time series spanning 60 days (5760 timestamps)
    with high completeness (>95%) for DO, temperature, and discharge.
    """
    dates = pd.date_range("2024-05-01", periods=5760, freq="15min", tz="UTC")
    np.random.seed(42)

    do = 8.5 + np.random.normal(0, 0.3, len(dates))
    temp = 19.0 + np.random.normal(0, 0.5, len(dates))
    q = 150.0 + np.random.normal(0, 5.0, len(dates))

    # Add a few isolated missing values (under 2%)
    do[np.random.choice(len(dates), 50, replace=False)] = np.nan
    temp[np.random.choice(len(dates), 30, replace=False)] = np.nan
    q[np.random.choice(len(dates), 40, replace=False)] = np.nan

    df = pd.DataFrame(
        {
            "dissolved_oxygen": do,
            "water_temperature": temp,
            "discharge": q,
            "turbidity": 5.0 + np.random.normal(0, 0.5, len(dates)),
        },
        index=dates,
    )

    metadata = {
        "station_id": "TEST_GOOD_01",
        "station_name": "SYNTHETIC HIGH-QUALITY RIVER GAGE",
        "latitude": 40.0,
        "longitude": -75.0,
        "available_parameters": {"00300": {}, "00010": {}, "00060": {}, "63680": {}},
    }
    return df, metadata


@pytest.fixture
def synthetic_sparse_station_data() -> tuple:
    """
    SYNTHETIC TEST DATA FIXTURE
    Generates time series with high missingness for DO (<40%) to test INSUFFICIENT classification.
    """
    dates = pd.date_range("2024-05-01", periods=1000, freq="15min", tz="UTC")
    do = np.full(len(dates), np.nan)
    do[:200] = 7.0  # Only 20% DO availability

    df = pd.DataFrame(
        {
            "dissolved_oxygen": do,
            "discharge": [50.0] * len(dates),
        },
        index=dates,
    )
    metadata = {
        "station_id": "TEST_SPARSE_02",
        "station_name": "SYNTHETIC SPARSE GAGE",
        "latitude": 38.0,
        "longitude": -77.0,
        "available_parameters": {"00300": {}, "00060": {}},
    }
    return df, metadata


def test_station_evaluator_good_classification(synthetic_complete_station_data):
    """Verifies that high-completeness multi-parameter dataset receives 'GOOD' suitability."""
    df, meta = synthetic_complete_station_data
    evaluator = StationEvaluator()
    result = evaluator.evaluate_station(df, meta)

    assert result["suitability_class"] == "GOOD"
    assert result["do_availability_pct"] > 80.0
    assert result["temp_availability_pct"] > 75.0
    assert result["discharge_availability_pct"] > 70.0
    assert result["longest_gap_days"] < 1.0


def test_station_evaluator_insufficient_classification(synthetic_sparse_station_data):
    """Verifies that low DO availability is categorized as 'INSUFFICIENT' with explicit reason."""
    df, meta = synthetic_sparse_station_data
    evaluator = StationEvaluator()
    result = evaluator.evaluate_station(df, meta)

    assert result["suitability_class"] == "INSUFFICIENT"
    assert "DO availability" in result["suitability_reason"]


def test_data_quality_analyzer_cooccurrence(synthetic_complete_station_data):
    """Verifies calculation of co-occurrence metrics between DO, temp, and discharge."""
    df, meta = synthetic_complete_station_data
    analyzer = DataQualityAnalyzer()
    quality = analyzer.evaluate_quality("TEST_GOOD_01", df, meta)

    assert quality["total_observations"] == 5760
    assert quality["temporal_frequency"] == "15-minute"
    assert quality["do_and_discharge_cooccurrence_pct"] > 95.0
    assert quality["do_temp_discharge_cooccurrence_pct"] > 95.0
