"""
AquaRehearsal-X - Stage 2.5 Extended Pipeline Tests
Verifies multi-year historical record, real precipitation integration,
storm feature construction, and temporal non-leakage.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.config.stage2_5_settings import (
    STAGE2_5_DATA_CONFIG,
    STAGE2_5_STORM_FEATURE_CONFIG,
    STAGE2_5_SPLIT_CONFIG,
    PROCESSED_DATA_DIR,
)
from src.features.storm_features import StormFeatureBuilder
from src.features.target_builder import TargetBuilder


@pytest.fixture
def extended_df():
    csv_path = PROCESSED_DATA_DIR / STAGE2_5_DATA_CONFIG["extended_data_file"]
    if not csv_path.exists():
        pytest.skip(f"Extended dataset {csv_path} does not exist yet.")
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def test_extended_dataset_temporal_depth(extended_df):
    """Verifies that extended dataset spans at least 3.5 years (2023 to 2026)."""
    start = extended_df["timestamp"].min()
    end = extended_df["timestamp"].max()
    span_days = (end - start).total_seconds() / 86400.0

    assert start.year == 2023, f"Expected start year 2023, got {start.year}"
    assert end.year == 2026, f"Expected end year 2026, got {end.year}"
    assert span_days > 1200, f"Expected > 1200 days of coverage, got {span_days:.1f}"
    assert len(extended_df) > 30000, f"Expected > 30,000 hourly rows, got {len(extended_df)}"


def test_rain_mm_column_and_missingness_integrity(extended_df):
    """
    Verifies that rain_mm exists as primary storm variable,
    contains both measured 0.0 dry hours and positive wet hours,
    and missing values remain strictly NaN (never converted to 0.0).
    """
    assert "rain_mm" in extended_df.columns, "rain_mm column missing from extended dataset"
    assert "precipitation_mm" in extended_df.columns, "precipitation_mm column missing"

    r = extended_df["rain_mm"]
    valid_count = int(r.notna().sum())
    missing_count = int(r.isna().sum())
    dry_count = int((r == 0.0).sum())
    wet_count = int((r > 0.0).sum())

    assert valid_count > 30000, "Expected > 30,000 valid rain observations"
    assert dry_count > 20000, "Expected majority of hours to be dry (0.0 mm)"
    assert wet_count > 2000, "Expected at least 2,000 wet hours (>0.0 mm)"
    # Missing hours exist at the end of the record (ERA5 latency) and MUST be NaN
    assert missing_count > 0, "Expected latency-related missing values at end of record"
    assert np.isnan(r.iloc[-1]), "End of record without meteorology must be NaN, not 0.0"


def test_storm_feature_separation_model_a_vs_model_b(extended_df):
    """
    Verifies strict separation of feature spaces:
    - Model A contains ONLY water/physicochemical/seasonal features (ZERO rainfall features).
    - Model B contains Model A features PLUS explicit storm rainfall features.
    """
    sample = extended_df.iloc[:500].copy()
    tgt_builder = TargetBuilder(horizon_hours=72, min_valid_hours=58)
    sample_tgt = tgt_builder.compute_72h_minimum_target(sample, output_col="target_min_do_72h")

    builder = StormFeatureBuilder()
    df_storm, model_a_cols, model_b_cols = builder.build_model_feature_matrices(sample_tgt)

    # Model A checks
    precip_keywords = ["rain", "precipitation", "antecedent"]
    for col in model_a_cols:
        for kw in precip_keywords:
            assert kw not in col.lower(), f"Leakage: Model A feature '{col}' contains precipitation keyword '{kw}'"

    # Model B checks
    rain_cols = [c for c in model_b_cols if "rain" in c.lower()]
    assert len(rain_cols) >= 8, f"Expected at least 8 storm rain features in Model B, got {len(rain_cols)}"
    assert len(model_b_cols) > len(model_a_cols), "Model B must have strictly more features than Model A"


def test_no_future_precipitation_leakage():
    """
    Verifies that rainfall rolling features at prediction time t do NOT peek into the future (t+1, t+2, etc.).
    """
    times = pd.date_range("2024-05-01 00:00:00", periods=10, freq="1h", tz="UTC")
    # Hourly rain pulse of 10 mm occurs ONLY at index 5
    rain_vals = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0]
    df = pd.DataFrame({"rain_mm": rain_vals, "dissolved_oxygen": [8.0] * 10, "water_temperature": [20.0] * 10, "discharge": [1000.0] * 10}, index=times)

    builder = StormFeatureBuilder()
    df_feats = builder.add_precipitation_features(df)

    # At t=4 (one hour BEFORE the storm pulse at t=5):
    # rain_1h, rain_roll_3h, rain_roll_6h must ALL be 0.0 (no future leakage!)
    assert df_feats.loc[times[4], "rain_1h"] == 0.0
    assert df_feats.loc[times[4], "rain_roll_3h"] == 0.0
    assert df_feats.loc[times[4], "rain_roll_6h"] == 0.0

    # At t=5 (the moment of the pulse):
    assert df_feats.loc[times[5], "rain_1h"] == 10.0
    assert df_feats.loc[times[5], "rain_roll_3h"] == 10.0
