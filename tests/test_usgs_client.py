"""
Tests for USGSClient and API response parsing.
All fixtures in this file are SYNTHETIC TEST DATA used solely for testing software behavior.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data.usgs_client import USGSClient


@pytest.fixture
def synthetic_usgs_payload() -> dict:
    """
    SYNTHETIC TEST DATA FIXTURE
    Models the JSON structure of a USGS NWIS Instantaneous Values response.
    """
    return {
        "provenance": {
            "source": "TEST FIXTURE - SYNTHETIC DATA",
            "station_id": "TEST_01000000",
        },
        "data": {
            "value": {
                "timeSeries": [
                    {
                        "sourceInfo": {
                            "siteName": "SYNTHETIC TEST STREAM AT LAB",
                            "siteCode": [{"value": "TEST_01000000"}],
                            "geoLocation": {
                                "geogLocation": {
                                    "latitude": 39.1234,
                                    "longitude": -76.5432,
                                }
                            },
                        },
                        "variable": {
                            "variableCode": [{"value": "00300"}],
                            "variableName": "Dissolved oxygen, water, unfiltered, mg/L",
                            "unit": {"unitCode": "mg/L"},
                        },
                        "values": [
                            {
                                "value": [
                                    {"value": "8.50", "dateTime": "2024-05-01T00:00:00.000-04:00", "qualifiers": ["A"]},
                                    {"value": "8.40", "dateTime": "2024-05-01T00:15:00.000-04:00", "qualifiers": ["A"]},
                                    {"value": "-999999", "dateTime": "2024-05-01T00:30:00.000-04:00", "qualifiers": ["P"]},
                                    {"value": "8.20", "dateTime": "2024-05-01T00:45:00.000-04:00", "qualifiers": ["A"]},
                                ]
                            }
                        ],
                    },
                    {
                        "sourceInfo": {
                            "siteName": "SYNTHETIC TEST STREAM AT LAB",
                            "siteCode": [{"value": "TEST_01000000"}],
                            "geoLocation": {
                                "geogLocation": {
                                    "latitude": 39.1234,
                                    "longitude": -76.5432,
                                }
                            },
                        },
                        "variable": {
                            "variableCode": [{"value": "00060"}],
                            "variableName": "Discharge, cubic feet per second",
                            "unit": {"unitCode": "cfs"},
                        },
                        "values": [
                            {
                                "value": [
                                    {"value": "120.5", "dateTime": "2024-05-01T00:00:00.000-04:00", "qualifiers": ["A"]},
                                    {"value": "122.0", "dateTime": "2024-05-01T00:15:00.000-04:00", "qualifiers": ["A"]},
                                    {"value": "130.0", "dateTime": "2024-05-01T00:30:00.000-04:00", "qualifiers": ["A"]},
                                    {"value": "145.2", "dateTime": "2024-05-01T00:45:00.000-04:00", "qualifiers": ["A"]},
                                ]
                            }
                        ],
                    },
                ]
            }
        },
    }


def test_parse_iv_response_metadata(synthetic_usgs_payload):
    """Verifies correct parsing of station metadata from response."""
    df, meta = USGSClient.parse_iv_response(synthetic_usgs_payload)

    assert meta["station_id"] == "TEST_01000000"
    assert meta["station_name"] == "SYNTHETIC TEST STREAM AT LAB"
    assert meta["latitude"] == 39.1234
    assert meta["longitude"] == -76.5432
    assert "00300" in meta["available_parameters"]
    assert "00060" in meta["available_parameters"]
    assert meta["available_parameters"]["00300"]["unit"] == "mg/L"


def test_parse_iv_response_data(synthetic_usgs_payload):
    """Verifies time-series conversion, timezone handling, and missing-value flags."""
    df, _ = USGSClient.parse_iv_response(synthetic_usgs_payload)

    assert len(df) == 4
    # Verify index is UTC DatetimeIndex
    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"

    # Verify column presence
    assert "dissolved_oxygen" in df.columns
    assert "discharge" in df.columns

    # Verify missing value code (-999999) was converted to NaN
    assert np.isnan(df.iloc[2]["dissolved_oxygen"])
    assert df.iloc[0]["dissolved_oxygen"] == 8.50
    assert df.iloc[3]["discharge"] == 145.2


def test_empty_response():
    """Verifies that an empty or missing response returns empty DataFrame without crashing."""
    df, meta = USGSClient.parse_iv_response({"data": {"value": {"timeSeries": []}}})
    assert df.empty
    assert meta["station_id"] is None
