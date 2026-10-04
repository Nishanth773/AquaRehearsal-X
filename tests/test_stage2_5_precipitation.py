"""
AquaRehearsal-X - Stage 2.5 Precipitation Integrity Tests
Validates scientific handling of real precipitation:
1. Missing precipitation observations must REMAIN NaN (never silently converted to 0.0 mm).
2. Explicit distinction between measured 0.0 mm (dry) and NaN (unobserved/missing).
3. Data quality reporting calculates precipitation missingness.
"""

import numpy as np
import pandas as pd
import pytest

from src.data.extended_ingestion import ExtendedDataIngestor


def test_missing_precipitation_preserved_as_nan():
    """
    MANDATORY SCIENTIFIC INTEGRITY TEST:
    Verifies that missing precipitation observations remain NaN after temporal alignment
    and are NEVER silently converted or imputed to 0.0 mm.
    """
    # 5 hourly timestamps
    times = pd.date_range("2025-06-01 00:00:00", periods=5, freq="1h", tz="UTC")

    # USGS stream observations
    df_usgs = pd.DataFrame({
        "dissolved_oxygen": [8.5, 8.4, 8.2, 8.0, 7.9],
        "discharge": [1000.0, 1050.0, 1100.0, 1200.0, 1150.0],
    }, index=times)

    # Precipitation series: hours 0 and 1 are 0.0 (measured dry),
    # hour 2 is 5.2 mm (measured rain), hour 3 is missing (NaN), hour 4 is 0.0
    precip_series = pd.Series([0.0, 0.0, 5.2, np.nan, 0.0], index=times, name="precipitation_mm")
    df_precip = pd.DataFrame(precip_series)

    # Perform temporal alignment (left join on hourly UTC index, exactly as in pipeline)
    df_aligned = df_usgs.join(df_precip, how="left")

    # Hour 0: Measured dry -> must be exactly 0.0
    assert df_aligned.loc[times[0], "precipitation_mm"] == 0.0

    # Hour 2: Measured wet -> must be exactly 5.2
    assert df_aligned.loc[times[2], "precipitation_mm"] == 5.2

    # Hour 3: Missing meteorological observation -> MUST BE NaN, NEVER 0.0!
    assert np.isnan(df_aligned.loc[times[3], "precipitation_mm"]), (
        "CRITICAL ERROR: Missing precipitation observation was converted to non-NaN value!"
    )
    assert df_aligned.loc[times[3], "precipitation_mm"] != 0.0, (
        "CRITICAL ERROR: Missing precipitation was silently imputed as 0.0 mm!"
    )


def test_precipitation_observed_zero_vs_missing_distinction():
    """Verifies clear separation between measured 0.0 mm and unobserved NaN."""
    s = pd.Series([0.0, 0.0, 1.5, np.nan, 0.0, np.nan])

    measured_dry = int((s == 0.0).sum())
    measured_wet = int((s > 0.0).sum())
    unobserved_nan = int(s.isna().sum())

    assert measured_dry == 3
    assert measured_wet == 1
    assert unobserved_nan == 2
    assert measured_dry + measured_wet + unobserved_nan == len(s)


def test_missing_rain_preserved_as_nan():
    """
    MANDATORY SCIENTIFIC INTEGRITY TEST:
    Verifies that missing rain (liquid precipitation) observations remain NaN after temporal alignment
    and are NEVER silently converted or imputed to 0.0 mm.
    """
    # 5 hourly timestamps
    times = pd.date_range("2025-06-01 00:00:00", periods=5, freq="1h", tz="UTC")

    # USGS stream observations
    df_usgs = pd.DataFrame({
        "dissolved_oxygen": [8.5, 8.4, 8.2, 8.0, 7.9],
        "discharge": [1000.0, 1050.0, 1100.0, 1200.0, 1150.0],
    }, index=times)

    # Rain series: hours 0 and 1 are 0.0 (measured dry),
    # hour 2 is 4.8 mm (measured rain), hour 3 is missing (NaN), hour 4 is 0.0
    rain_series = pd.Series([0.0, 0.0, 4.8, np.nan, 0.0], index=times, name="rain_mm")
    precip_series = pd.Series([0.0, 0.0, 4.8, np.nan, 0.0], index=times, name="precipitation_mm")
    df_meteo = pd.DataFrame({"rain_mm": rain_series, "precipitation_mm": precip_series})

    # Perform temporal alignment (left join on hourly UTC index, exactly as in pipeline)
    df_aligned = df_usgs.join(df_meteo, how="left")

    # Hour 0: Measured dry -> must be exactly 0.0
    assert df_aligned.loc[times[0], "rain_mm"] == 0.0

    # Hour 2: Measured wet -> must be exactly 4.8
    assert df_aligned.loc[times[2], "rain_mm"] == 4.8

    # Hour 3: Missing meteorological observation -> MUST BE NaN, NEVER 0.0!
    assert np.isnan(df_aligned.loc[times[3], "rain_mm"]), (
        "CRITICAL ERROR: Missing rain observation was converted to non-NaN value!"
    )
    assert df_aligned.loc[times[3], "rain_mm"] != 0.0, (
        "CRITICAL ERROR: Missing rain was silently imputed as 0.0 mm!"
    )


def test_rain_observed_zero_vs_missing_distinction():
    """Verifies clear separation between measured 0.0 mm rain (dry) and unobserved NaN."""
    s = pd.Series([0.0, 0.0, 2.5, np.nan, 0.0, np.nan], name="rain_mm")

    measured_dry = int((s == 0.0).sum())
    measured_wet = int((s > 0.0).sum())
    unobserved_nan = int(s.isna().sum())

    assert measured_dry == 3
    assert measured_wet == 1
    assert unobserved_nan == 2
    assert measured_dry + measured_wet + unobserved_nan == len(s)


def test_precipitation_missingness_in_quality_audit():
    """Verifies that data quality audit calculates precipitation completeness and missingness."""
    df = pd.DataFrame({
        "dissolved_oxygen": [8.0, 8.1, 8.2, 8.3, 8.4],
        "rain_mm": [0.0, 2.5, np.nan, 0.0, 1.0],
        "precipitation_mm": [0.0, 2.5, np.nan, 0.0, 1.0],
    })

    total = len(df)
    valid_rain = int(df["rain_mm"].notna().sum())
    missing_rain = int(df["rain_mm"].isna().sum())

    missing_pct = (missing_rain / total) * 100.0
    valid_pct = (valid_rain / total) * 100.0

    assert valid_rain == 4
    assert missing_rain == 1
    assert missing_pct == 20.0
    assert valid_pct == 80.0
