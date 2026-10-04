"""
AquaRehearsal-X - Configuration Settings
Stage 1: Real Data Foundation

All criteria thresholds, parameter codes, and system paths are defined here.
No scientific thresholds or criteria are hard-coded in business logic.
"""

from pathlib import Path
from typing import Dict, List, Any

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"
PLOTS_DIR = REPORTS_DIR / "plots"

# Ensure essential directories exist
for directory in [RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, PLOTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# USGS Parameter Codes
# Official USGS parameter codes for aquatic monitoring
USGS_PARAM_CODES: Dict[str, Dict[str, str]] = {
    "00300": {
        "name": "dissolved_oxygen",
        "description": "Dissolved oxygen, water, unfiltered, milligrams per liter (mg/L)",
        "unit": "mg/L",
        "min_valid": 0.0,
        "max_valid": 25.0,  # Physical saturation limit in natural freshwaters
    },
    "00010": {
        "name": "water_temperature",
        "description": "Temperature, water, degrees Celsius (°C)",
        "unit": "deg_C",
        "min_valid": -2.0,
        "max_valid": 45.0,
    },
    "00060": {
        "name": "discharge",
        "description": "Discharge, cubic feet per second (cfs)",
        "unit": "cfs",
        "min_valid": 0.0,
        "max_valid": 500000.0,
    },
    "00076": {
        "name": "turbidity_00076",
        "description": "Turbidity, water, unfiltered, nephelometric turbidity units (NTU)",
        "unit": "NTU",
        "min_valid": 0.0,
        "max_valid": 4000.0,
    },
    "63680": {
        "name": "turbidity_63680",
        "description": "Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 +/-2.5 degrees, formazin nephelometric units (FNU)",
        "unit": "FNU",
        "min_valid": 0.0,
        "max_valid": 4000.0,
    },
    "00065": {
        "name": "gage_height",
        "description": "Gage height, feet",
        "unit": "ft",
        "min_valid": 0.0,
        "max_valid": 100.0,
    },
}

# Standardized column mappings
PARAM_CODE_TO_COLUMN: Dict[str, str] = {
    "00300": "dissolved_oxygen",
    "00010": "water_temperature",
    "00060": "discharge",
    "00076": "turbidity",
    "63680": "turbidity",
    "00065": "gage_height",
}

# Candidate Station Suitability Evaluation Criteria
# Explicit numerical thresholds for categorizing candidate stations
SUITABILITY_CRITERIA: Dict[str, Any] = {
    "good": {
        "min_do_availability_pct": 80.0,
        "min_temp_availability_pct": 75.0,
        "min_discharge_availability_pct": 70.0,
        "max_continuous_gap_days": 14.0,
        "min_observations": 5000,
    },
    "warning": {
        "min_do_availability_pct": 50.0,
        "min_temp_availability_pct": 50.0,
        "min_discharge_availability_pct": 40.0,
        "max_continuous_gap_days": 45.0,
        "min_observations": 1000,
    },
    # Anything below warning thresholds or missing DO completely is classified as INSUFFICIENT
}

# Disturbance / Candidate Storm Event Detection Parameters
DISTURBANCE_CONFIG: Dict[str, Any] = {
    # Peak discharge must be at least this factor times the rolling median baseline
    "discharge_spike_multiplier": 2.5,
    # Or absolute discharge quantile threshold across the series
    "discharge_quantile_threshold": 0.90,
    # Minimum hours between separate candidate storm events
    "min_event_separation_hours": 36,
    # Pre-event baseline window (hours before peak)
    "pre_event_window_hours": 24,
    # Post-event recovery window (hours after peak)
    "post_event_window_hours": 72,
}

# Resampling Configurations
RESAMPLING_CONFIG: Dict[str, Any] = {
    "default_resolution": "native",
    "supported_resolutions": ["native", "15min", "1H", "1D"],
    "aggregations": {
        "dissolved_oxygen": "mean",
        "water_temperature": "mean",
        "discharge": "mean",
        "turbidity": "mean",
        "gage_height": "mean",
    },
}

# Default API endpoints
USGS_IV_URL = "https://waterservices.usgs.gov/nwis/iv/"
USGS_SITE_URL = "https://waterservices.usgs.gov/nwis/site/"
