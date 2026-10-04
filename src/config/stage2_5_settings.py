"""
AquaRehearsal-X - Configuration Settings for Stage 2.5
Historical Depth + Real Precipitation Upgrade

Defines extended multi-year date boundaries, precipitation feature specifications,
storm event detection thresholds, and model training configurations for:
- MODEL A: Water-Only
- MODEL B: Water + Precipitation
"""

from pathlib import Path
from typing import Dict, List, Any

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"
STAGE2_5_REPORTS_DIR = REPORTS_DIR / "stage2_5"
STAGE2_5_MODELS_DIR = STAGE2_5_REPORTS_DIR / "models"
STAGE2_5_PLOTS_DIR = STAGE2_5_REPORTS_DIR

# Ensure output directories exist
for directory in [STAGE2_5_REPORTS_DIR, STAGE2_5_MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Station and Extended Data File Configuration
STAGE2_5_DATA_CONFIG: Dict[str, Any] = {
    "station_id": "01474500",
    "station_name": "Schuylkill River at Philadelphia, PA",
    "extended_data_file": "station_01474500_extended_1h.csv",
    "stage2_baseline_data_file": "station_01474500_1h.csv",
    "temporal_resolution": "1h",
    "random_seed": 42,
}

# Precipitation Source Documentation Metadata
PRECIPITATION_METADATA: Dict[str, Any] = {
    "source": "Open-Meteo Historical Weather API",
    "exact_model_dataset": "ECMWF ERA5 Reanalysis (era5)",
    "requested_latitude": 39.96779,
    "requested_longitude": -75.18850,
    "returned_grid_latitude": 40.0,
    "returned_grid_longitude": -75.25,
    "returned_grid_elevation_m": 2.0,
    "spatial_resolution": "0.25 degree (~25-30 km grid cell)",
    "temporal_resolution": "1h (hourly)",
    "units": "millimeters (mm)",
    "primary_variable": "rain_mm (liquid precipitation, mm)",
    "secondary_variable": "precipitation_mm (total liquid + solid water equivalent, mm)",
    "missing_value_convention": "Missing precipitation/rain = NaN; observed dry hour = 0.0 mm. Never convert missing to zero.",
    "geographic_scope_note": (
        "Precipitation and rain data represent ECMWF ERA5 gridded atmospheric reanalysis estimates "
        "at grid cell Lat 40.0° N, Lon -75.25° W and are NOT equivalent to watershed-average rainfall "
        "across the 1,893 sq mi Schuylkill River catchment."
    ),
}

# Chronological Validation Split Configuration (Multi-Year)
STAGE2_5_SPLIT_CONFIG: Dict[str, str] = {
    "train_start": "2023-01-01 05:00:00+00:00",
    "train_end": "2025-06-30 23:00:00+00:00",
    "val_start": "2025-07-01 00:00:00+00:00",
    "val_end": "2026-03-31 23:00:00+00:00",
    "test_start": "2026-04-01 00:00:00+00:00",
    "test_end": "2026-09-25 15:00:00+00:00",
    # Stage 2 identical test subset for 1:1 direct comparability
    "stage2_exact_test_start": "2026-08-25 00:00:00+00:00",
    "stage2_exact_test_end": "2026-09-25 15:00:00+00:00",
}

# Target Definition (identical to Stage 2)
STAGE2_5_TARGET_CONFIG: Dict[str, Any] = {
    "target_name": "target_min_do_72h",
    "forecast_horizon_hours": 72,
    "min_valid_future_ratio": 0.80,
    "min_valid_future_hours": 58,
}

# Storm & Precipitation Feature Engineering Configuration
STAGE2_5_STORM_FEATURE_CONFIG: Dict[str, Any] = {
    "primary_rain_col": "rain_mm",
    "precipitation_col": "precipitation_mm",
    "precip_rolling_windows": ["3h", "6h", "12h", "24h", "48h", "72h"],
    "precip_intensity_windows": ["6h", "24h"],
    "antecedent_window_days": 7,
    "discharge_change_hours": [1, 3, 6, 24],
    "turbidity_change_hours": [6, 24],
}

# Model Hyperparameters
STAGE2_5_MODEL_CONFIG: Dict[str, Any] = {
    "lgbm_params": {
        "objective": "regression",
        "metric": "rmse",
        "n_estimators": 400,
        "learning_rate": 0.03,
        "max_depth": 6,
        "num_leaves": 31,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "random_state": 42,
        "n_jobs": -1,
        "verbose": -1,
    },
    "lgbm_early_stopping_rounds": 35,
    "uncertainty_quantiles": [0.10, 0.50, 0.90],
    "conformal_nominal_coverage": 0.80,
}
