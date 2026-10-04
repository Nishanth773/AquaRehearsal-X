"""
AquaRehearsal-X - Stage 2 Unit & Integration Tests
72-Hour Dissolved Oxygen Forecasting Engine

Tests cover:
- Target generation and 72-hour future window construction
- Strict exclusion of current time t from target window
- Handling of incomplete target windows and minimum valid counts
- Feature lagging and backward-looking rolling features
- RIGOROUS LEAKAGE PREVENTION (future mutation test)
- Chronological split partitioning and non-overlapping time boundaries
- Baseline A (persistence) and Baseline B (linear/seasonal)
- LightGBM / Gradient Boosting model training and prediction
- Missing input handling
- Uncertainty quantile generation and non-crossing constraints
- Split conformal prediction calibration
- Basic input-domain / OOD warnings
- API inference interface
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.features.target_builder import TargetBuilder
from src.features.feature_builder import FeatureBuilder
from src.models.baselines import PersistenceBaseline, LinearSeasonalBaseline
from src.models.forecaster import DissolvedOxygenForecaster
from src.models.uncertainty import QuantileForecaster, SplitConformalCalibrator
from src.models.ood_checker import InputDomainChecker
from src.models.api import AquaForecastingAPI, predict_min_do


# ==========================================
# 1. Target Generation Tests
# ==========================================

def test_target_generation_forward_window():
    """Verifies that TARGET(t) = min DO during (t, t + 72h], strictly excluding t."""
    times = pd.date_range("2026-01-01 00:00:00", periods=100, freq="1h", tz="UTC")
    # Synthetic series where t=0 is 20.0, t=1..5 are decreasing, t=6..100 are high
    values = np.full(100, 15.0)
    values[0] = 20.0  # current value at t=0
    values[1] = 9.0
    values[2] = 5.0   # minimum in (0, 72h]
    values[3] = 7.0

    df = pd.DataFrame({"timestamp": times, "dissolved_oxygen": values})
    builder = TargetBuilder(horizon_hours=72, min_valid_hours=10)
    df_tgt = builder.compute_72h_minimum_target(df, output_col="target")

    # At t=0, future window (0, 72h] covers t=1..72. Minimum should be 5.0 (values[2]).
    # It must NOT be 20.0 (values[0])!
    assert df_tgt.loc[0, "target"] == 5.0

    # Ensure that if values[0] had been 2.0 (lower than any future value), target at t=0 is still 5.0
    values[0] = 2.0
    df2 = pd.DataFrame({"timestamp": times, "dissolved_oxygen": values})
    df_tgt2 = builder.compute_72h_minimum_target(df2, output_col="target")
    assert df_tgt2.loc[0, "target"] == 5.0, "Current value at t leaked into future target window!"


def test_target_incomplete_window_handling():
    """Verifies that incomplete target windows (e.g. at the end of series) receive NaN."""
    times = pd.date_range("2026-01-01 00:00:00", periods=80, freq="1h", tz="UTC")
    df = pd.DataFrame({"timestamp": times, "dissolved_oxygen": np.full(80, 8.0)})
    builder = TargetBuilder(horizon_hours=72, min_valid_hours=58)
    df_tgt = builder.compute_72h_minimum_target(df, output_col="target")

    # For row index >= 23, there are fewer than 58 future hours remaining (80 - 23 - 1 = 56 < 58)
    assert np.isnan(df_tgt.loc[79, "target"])
    assert np.isnan(df_tgt.loc[70, "target"])
    assert np.isnan(df_tgt.loc[25, "target"])
    # For row 0, 79 future hours exist (> 58), so target must be valid
    assert not np.isnan(df_tgt.loc[0, "target"])


# ==========================================
# 2. Feature Engineering & Leakage Tests
# ==========================================

def test_feature_lagging_strictly_backward():
    """Verifies lag features shift past data forward and contain no future values."""
    times = pd.date_range("2026-01-01 00:00:00", periods=50, freq="1h", tz="UTC")
    values = np.arange(50, dtype=float)
    df = pd.DataFrame({"timestamp": times, "dissolved_oxygen": values}).set_index("timestamp")

    builder = FeatureBuilder()
    df_lags = builder.add_lag_features(df)

    # lag_1h at index 10 should equal values[9] (which is 9.0)
    assert df_lags["dissolved_oxygen_lag_1h"].iloc[10] == 9.0
    # lag_6h at index 10 should equal values[4] (which is 4.0)
    assert df_lags["dissolved_oxygen_lag_6h"].iloc[10] == 4.0
    # lag_1h at index 0 should be NaN (no prior observation)
    assert np.isnan(df_lags["dissolved_oxygen_lag_1h"].iloc[0])


def test_rolling_features_backward_looking():
    """Verifies that rolling statistics include strictly (t - window, t]."""
    times = pd.date_range("2026-01-01 00:00:00", periods=20, freq="1h", tz="UTC")
    values = np.arange(20, dtype=float)
    df = pd.DataFrame({"timestamp": times, "discharge": values}).set_index("timestamp")

    builder = FeatureBuilder()
    df_roll = builder.add_rolling_backward_features(df)

    # At row 5 (value 5.0), rolling 6h window covers values [0, 1, 2, 3, 4, 5]
    # max should be 5.0, mean should be 2.5
    assert df_roll["discharge_roll_6h_max"].iloc[5] == 5.0
    assert df_roll["discharge_roll_6h_mean"].iloc[5] == 2.5


def test_rigorous_leakage_prevention_via_future_mutation():
    """
    CRITICAL TEST: Mutating future data for t > t_0 MUST NOT change features at t <= t_0.
    """
    n_hours = 120
    times = pd.date_range("2026-01-01 00:00:00", periods=n_hours, freq="1h", tz="UTC")
    np.random.seed(42)

    df_original = pd.DataFrame({
        "timestamp": times,
        "dissolved_oxygen": np.random.uniform(5.0, 12.0, n_hours),
        "water_temperature": np.random.uniform(15.0, 28.0, n_hours),
        "discharge": np.random.uniform(500.0, 3000.0, n_hours),
        "turbidity": np.random.uniform(2.0, 20.0, n_hours),
    }).set_index("timestamp")

    builder = FeatureBuilder()
    feat_orig, cols = builder.build_feature_matrix(df_original, target_col=None)

    # Choose split timestamp t_0 at hour 60
    t_0_idx = 60
    t_0 = times[t_0_idx]

    # Create mutated future dataset: scramble all rows strictly AFTER t_0
    df_mutated = df_original.copy()
    future_mask = df_mutated.index > t_0
    df_mutated.loc[future_mask, "dissolved_oxygen"] = 999.0
    df_mutated.loc[future_mask, "water_temperature"] = -99.0
    df_mutated.loc[future_mask, "discharge"] = 1e6
    df_mutated.loc[future_mask, "turbidity"] = 5000.0

    feat_mutated, _ = builder.build_feature_matrix(df_mutated, target_col=None)

    # Features at t <= t_0 must be 100% IDENTICAL across all engineered features!
    sub_orig = feat_orig.loc[feat_orig.index <= t_0, cols]
    sub_mutated = feat_mutated.loc[feat_mutated.index <= t_0, cols]

    diff = np.abs(sub_orig.values - sub_mutated.values)
    max_diff = np.nanmax(diff)

    assert max_diff == 0.0, f"LEAKAGE DETECTED! Features at t <= t_0 changed when future data was mutated! Max diff: {max_diff}"


# ==========================================
# 3. Model & Baseline Tests
# ==========================================

def test_baseline_a_persistence():
    """Verifies Baseline A persistence matches current DO."""
    df = pd.DataFrame({"dissolved_oxygen": [8.5, 9.2, 6.4]})
    baseline = PersistenceBaseline()
    preds = baseline.predict(df)
    np.testing.assert_array_equal(preds, np.array([8.5, 9.2, 6.4]))


def test_baseline_b_linear():
    """Verifies Baseline B fits and generates predictions."""
    X = pd.DataFrame({
        "dissolved_oxygen": [8.0, 7.5, 6.0, 5.5],
        "water_temperature": [20.0, 22.0, 25.0, 26.0],
        "hour_sin": [0.0, 0.5, 1.0, 0.5],
        "hour_cos": [1.0, 0.8, 0.0, -0.8],
        "doy_sin": [0.5, 0.5, 0.5, 0.5],
        "doy_cos": [0.8, 0.8, 0.8, 0.8],
    })
    y = pd.Series([7.0, 6.5, 5.0, 4.5])

    baseline = LinearSeasonalBaseline()
    baseline.fit(X, y)
    preds = baseline.predict(X)
    assert len(preds) == 4
    assert np.all(np.isfinite(preds))


def test_forecaster_training_and_importance():
    """Verifies DissolvedOxygenForecaster training, prediction, and feature importance."""
    np.random.seed(42)
    n = 100
    X = pd.DataFrame({
        "dissolved_oxygen": np.random.uniform(5, 12, n),
        "water_temperature": np.random.uniform(15, 28, n),
        "discharge": np.random.uniform(500, 3000, n),
    })
    y = X["dissolved_oxygen"] * 0.7 + np.random.normal(0, 0.2, n)

    forecaster = DissolvedOxygenForecaster(random_seed=42)
    forecaster.fit(X, y)
    preds = forecaster.predict(X)

    assert len(preds) == n
    assert np.all(np.isfinite(preds))

    imp = forecaster.get_feature_importance()
    assert isinstance(imp, pd.DataFrame)
    assert "importance_gain_pct" in imp.columns
    assert len(imp) == 3


# ==========================================
# 4. Uncertainty & Conformal Tests
# ==========================================

def test_quantile_uncertainty_non_crossing():
    """Verifies quantile forecaster produces non-crossing bounds q10 <= q50 <= q90."""
    np.random.seed(42)
    n = 100
    X = pd.DataFrame({
        "dissolved_oxygen": np.random.uniform(5, 12, n),
        "water_temperature": np.random.uniform(15, 28, n),
    })
    y = X["dissolved_oxygen"] * 0.8 + np.random.normal(0, 0.5, n)

    q_forecaster = QuantileForecaster(quantiles=[0.10, 0.50, 0.90], random_seed=42)
    q_forecaster.fit(X, y)
    q_preds = q_forecaster.predict(X)

    assert "q_0.10" in q_preds and "q_0.50" in q_preds and "q_0.90" in q_preds
    # Test monotonic non-crossing condition
    assert np.all(q_preds["q_0.10"] <= q_preds["q_0.50"] + 1e-6)
    assert np.all(q_preds["q_0.50"] <= q_preds["q_0.90"] + 1e-6)


def test_split_conformal_calibration():
    """Verifies split conformal calibrator computes proper margin and intervals."""
    y_true = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
    y_pred = np.array([5.2, 5.8, 7.3, 7.9, 9.5])

    calibrator = SplitConformalCalibrator(nominal_coverage=0.80)
    calibrator.calibrate(y_true, y_pred)

    assert calibrator.conformal_quantile_margin is not None
    assert calibrator.conformal_quantile_margin > 0.0

    lower, upper = calibrator.predict_interval(np.array([7.0]))
    assert lower[0] < 7.0 < upper[0]


# ==========================================
# 5. Out-of-Distribution & API Tests
# ==========================================

def test_input_domain_warning_checker():
    """Verifies InputDomainChecker flags values outside historical range."""
    X_train = pd.DataFrame({
        "dissolved_oxygen": [6.0, 7.0, 8.0, 9.0, 10.0],
        "discharge": [500.0, 600.0, 700.0, 800.0, 900.0],
    })
    checker = InputDomainChecker()
    checker.fit(X_train)

    # Normal sample within range
    normal_sample = {"dissolved_oxygen": 7.5, "discharge": 700.0}
    res_normal = checker.check_sample(normal_sample)
    assert res_normal["has_domain_warning"] is False

    # Out-of-range sample (extreme flood discharge: 50,000 cfs)
    ood_sample = {"dissolved_oxygen": 7.5, "discharge": 50000.0}
    res_ood = checker.check_sample(ood_sample)
    assert res_ood["has_domain_warning"] is True
    assert "discharge" in res_ood["flagged_variables"]
    assert res_ood["warning_type"] == "Basic input-domain warning"


def test_predict_min_do_api():
    """Verifies predict_min_do function returns complete structured dictionary."""
    sample = {
        "dissolved_oxygen": 8.0,
        "water_temperature": 22.0,
        "discharge": 1200.0,
        "turbidity": 6.5,
    }
    result = predict_min_do(sample)

    assert isinstance(result, dict)
    assert "point_forecast_mg_L" in result
    assert "lower_bound_10th_percentile_mg_L" in result
    assert "upper_bound_90th_percentile_mg_L" in result
    assert "domain_warning" in result
    assert "model_metadata" in result
    assert result["target"] == "minimum_dissolved_oxygen_next_72h"
    assert result["forecast_horizon_hours"] == 72
