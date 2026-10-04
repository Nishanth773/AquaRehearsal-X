"""
Tests for DataCleaner and DataCleaningAudit.
All fixtures in this file are SYNTHETIC TEST DATA used solely for testing software behavior.
"""

import numpy as np
import pandas as pd
import pytest

from src.data.cleaner import DataCleaner


@pytest.fixture
def synthetic_dirty_dataframe() -> pd.DataFrame:
    """
    SYNTHETIC TEST DATA FIXTURE
    Constructs a DataFrame with deliberate anomalies:
    - Unsorted timestamps
    - Duplicate timestamps
    - Unlocalized timezones
    - Physical boundary violations (negative DO, extreme temp)
    """
    timestamps = [
        "2024-06-01 10:00:00",
        "2024-06-01 10:15:00",
        "2024-06-01 10:15:00",  # Duplicate timestamp
        "2024-06-01 09:45:00",  # Out of order timestamp
        "2024-06-01 10:30:00",
        "2024-06-01 10:45:00",
    ]
    df = pd.DataFrame(
        {
            "dissolved_oxygen": [8.0, 7.8, 7.9, 8.2, -1.5, 9.1],  # -1.5 is physically invalid
            "water_temperature": [20.1, 20.3, 20.3, 19.9, 21.0, 95.0],  # 95.0 is physically invalid
            "discharge": [50.0, 52.0, 52.0, 48.0, 55.0, 56.0],
        },
        index=pd.to_datetime(timestamps),
    )
    return df


def test_cleaner_duplicate_handling(synthetic_dirty_dataframe):
    """Verifies that duplicate timestamps are resolved and recorded in audit log."""
    cleaner = DataCleaner()
    cleaned, audit = cleaner.clean_timeseries(synthetic_dirty_dataframe)

    assert not cleaned.index.duplicated().any()
    assert len(cleaned) == 5  # 6 rows minus 1 duplicate = 5 rows

    # Check audit recorded duplicate resolution
    actions = [log["action"] for log in audit.logs]
    assert "DUPLICATES_RESOLVED" in actions


def test_cleaner_chronological_sorting(synthetic_dirty_dataframe):
    """Verifies that timestamps are monotonically increasing after cleaning."""
    cleaner = DataCleaner()
    cleaned, audit = cleaner.clean_timeseries(synthetic_dirty_dataframe)

    assert cleaned.index.is_monotonic_increasing
    actions = [log["action"] for log in audit.logs]
    assert "CHRONOLOGICAL_SORT" in actions


def test_cleaner_physical_boundary_violations(synthetic_dirty_dataframe):
    """Verifies that physical violations are set to NaN and flagged, not silently deleted."""
    cleaner = DataCleaner()
    cleaned, audit = cleaner.clean_timeseries(synthetic_dirty_dataframe)

    # -1.5 DO should become NaN
    assert np.isnan(cleaned.loc["2024-06-01 10:30:00+00:00", "dissolved_oxygen"])
    # 95.0 Temp should become NaN
    assert np.isnan(cleaned.loc["2024-06-01 10:45:00+00:00", "water_temperature"])

    # Audit log should capture both violations
    actions = [log["action"] for log in audit.logs]
    assert "PHYSICAL_BOUND_VIOLATION_LOW" in actions
    assert "PHYSICAL_BOUND_VIOLATION_HIGH" in actions
