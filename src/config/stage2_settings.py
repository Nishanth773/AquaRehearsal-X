"""
AquaRehearsal-X - Configuration Settings for Stage 2
72-Hour Dissolved Oxygen Forecasting Engine

Defines all target definitions, temporal horizons, chronological split boundaries,
feature engineering specifications, model hyperparameters, and uncertainty levels.
No scientific thresholds or criteria are hard-coded in business logic.
"""

from pathlib import Path
from typing import Dict, List, Any

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"
STAGE2_REPORTS_DIR = REPORTS_DIR / "stage2"
STAGE2_MODELS_DIR = STAGE2_REPORTS_DIR / "models"
STAGE2_PLOTS_DIR = STAGE2_REPORTS_DIR

# Ensure output directories exist
for directory in [STAGE2_REPORTS_DIR, STAGE2_MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Station and Temporal Configuration
STAGE2_STATION_CONFIG: Dict[str, Any] = {
    "primary_station_id": "01474500",
    "primary_station_name": "Schuylkill River at Philadelphia, PA",
    "primary_data_file": "station_01474500_1h.csv",
    "temporal_resolution": "1h",
    "random_seed": 42,
}

# Target Definition Configuration
STAGE2_TARGET_CONFIG: Dict[str, Any] = {
    "target_name": "target_min_do_72h",
    "target_description": "Minimum observed dissolved oxygen (mg/L) during the future window (t, t + 72 hours]",
    "forecast_horizon_hours": 72,
    # Minimum valid future observation ratio required to compute target (80% of 72h = 58h)
    "min_valid_future_ratio": 0.80,
    "min_valid_future_hours": 58,
}

# Chronological Validation Split Configuration
STAGE2_SPLIT_CONFIG: Dict[str, str] = {
    "train_start": "2026-04-01 16:00:00+00:00",
    "train_end": "2026-07-20 00:00:00+00:00",
    "val_start": "2026-07-20 00:00:00+00:00",
    "val_end": "2026-08-25 00:00:00+00:00",
    "test_start": "2026-08-25 00:00:00+00:00",
    "test_end": "2026-09-25 15:00:00+00:00",
}

# Feature Engineering Configuration
STAGE2_FEATURE_CONFIG: Dict[str, Any] = {
    "base_sensor_columns": [
        "dissolved_oxygen",
        "water_temperature",
        "discharge",
        "turbidity",
    ],
    # Backward lag steps (in hours for 1h resolution)
    "lag_hours": [1, 2, 3, 6, 12, 24, 48, 72],
    # Backward rolling statistics windows
    "rolling_windows": ["6h", "12h", "24h", "48h", "72h"],
    "rolling_stats": ["mean", "min", "max", "std"],
    # Recent backward change differences: X(t) - X(t - k)
    "change_hours": [1, 3, 6, 24],
    # Cyclical & seasonal encodings
    "include_diurnal": True,
    "include_annual": True,
    "include_physical_saturation": True,
}

# Model Hyperparameters
STAGE2_MODEL_CONFIG: Dict[str, Any] = {
    "lgbm_params": {
        "objective": "regression",
        "metric": "rmse",
        "n_estimators": 300,
        "learning_rate": 0.03,
        "max_depth": 5,
        "num_leaves": 31,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "random_state": 42,
        "n_jobs": -1,
        "verbose": -1,
    },
    "lgbm_early_stopping_rounds": 30,
    # Quantiles for uncertainty estimation (10th percentile = lower, 50th = median, 90th = upper)
    "uncertainty_quantiles": [0.10, 0.50, 0.90],
    # Nominal coverage for conformal prediction
    "conformal_nominal_coverage": 0.80,
}
