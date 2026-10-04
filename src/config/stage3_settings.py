"""
AquaRehearsal-X - Stage 3 Configuration Settings
Storm Tolerance Envelope (STE), Dynamic Conditioning & Early-Warning Infrastructure

Defines regulatory dissolved oxygen standards (PA DEP / EPA), thermal tiers,
antecedent moisture classifications, operational early-warning thresholds,
and path specifications for Stage 3 deliverables.
"""

from pathlib import Path
from typing import Dict, Any, List

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

STAGE2_5_REPORTS_DIR = REPORTS_DIR / "stage2_5"
STAGE2_5_MODELS_DIR = STAGE2_5_REPORTS_DIR / "models"

STAGE3_REPORTS_DIR = REPORTS_DIR / "stage3"
STAGE3_MODELS_DIR = STAGE3_REPORTS_DIR / "models"
STAGE3_PLOTS_DIR = STAGE3_REPORTS_DIR

# Ensure Stage 3 directories exist
for directory in [STAGE3_REPORTS_DIR, STAGE3_MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Station and Input Datasets
STAGE3_DATA_CONFIG: Dict[str, Any] = {
    "station_id": "01474500",
    "station_name": "Schuylkill River at Philadelphia, PA",
    "extended_data_file": "station_01474500_extended_1h.csv",
    "historical_events_file": "historical_storm_events.csv",
    "stage2_5_metadata_file": "stage2_5_metadata.json",
    "temporal_resolution": "1h",
    "drainage_area_sq_mi": 1893.0,
    "random_seed": 42,
}

# Regulatory & Ecological Dissolved Oxygen Thresholds (mg/L)
# Based on Pennsylvania Code Title 25 Chapter 93 Water Quality Standards
# (Warm Water Fishes - WWF criteria for Schuylkill River / Delaware Estuary Zone 3)
STAGE3_REGULATORY_THRESHOLDS: Dict[str, float] = {
    "standard_protection": 5.0,  # PA DEP daily average criterion (protective boundary)
    "acute_stress": 4.0,         # PA DEP minimum instantaneous criterion (acute threshold)
    "severe_hypoxia": 2.0,       # EPA / Ecological mortality limit (acute fish kill threshold)
}

# Thermal Conditioning Tiers (°C)
# Physical rationale: Oxygen saturation drops from ~13.8 mg/L at 2°C to ~8.1 mg/L at 26°C.
# Biological respiration rate roughly doubles per 10°C rise (van 't Hoff / Arrhenius Q10 ~ 2).
THERMAL_TIERS: Dict[str, Dict[str, Any]] = {
    "cold": {
        "name": "Cold Water Regime (<15°C)",
        "min_temp": -5.0,
        "max_temp": 15.0,
        "typical_saturation_mg_L": 11.5,
        "tolerance_capacity": "High assimilative buffer",
    },
    "moderate": {
        "name": "Moderate Water Regime (15°C - 22°C)",
        "min_temp": 15.0,
        "max_temp": 22.0,
        "typical_saturation_mg_L": 9.5,
        "tolerance_capacity": "Intermediate buffer",
    },
    "warm": {
        "name": "Warm Water Regime (>=22°C)",
        "min_temp": 22.0,
        "max_temp": 40.0,
        "typical_saturation_mg_L": 8.0,
        "tolerance_capacity": "Critically contracted buffer; elevated hypoxia vulnerability",
    },
}

# Antecedent Moisture Conditioning Tiers (72-hour antecedent rainfall in mm)
ANTECEDENT_MOISTURE_TIERS: Dict[str, Dict[str, Any]] = {
    "dry": {
        "name": "Dry Antecedent Catchment (<5 mm in 72h)",
        "min_api_mm": 0.0,
        "max_api_mm": 5.0,
        "runoff_modifier": 0.85,
    },
    "normal": {
        "name": "Normal Antecedent Catchment (5 - 20 mm in 72h)",
        "min_api_mm": 5.0,
        "max_api_mm": 20.0,
        "runoff_modifier": 1.0,
    },
    "wet": {
        "name": "Saturated Antecedent Catchment (>=20 mm in 72h)",
        "min_api_mm": 20.0,
        "max_api_mm": 500.0,
        "runoff_modifier": 1.35,
    },
}

# Operational Early Warning Alert Levels
EARLY_WARNING_LEVELS: Dict[str, Dict[str, Any]] = {
    "NORMAL": {
        "level": 0,
        "label": "NORMAL / SAFE",
        "color": "#2ca02c",  # Green
        "description": "Stream possesses ample assimilative capacity. DO expected to remain well above 5.0 mg/L.",
        "p_crossing_acute_max": 0.10,
        "expected_min_do_min": 5.0,
    },
    "ADVISORY": {
        "level": 1,
        "label": "ADVISORY / WATCH",
        "color": "#ff7f0e",  # Amber/Orange
        "description": "Dissolved oxygen may dip into regulatory concern zone (4.0 - 5.0 mg/L). Monitor telemetry.",
        "p_crossing_acute_min": 0.10,
        "p_crossing_acute_max": 0.35,
    },
    "WARNING": {
        "level": 2,
        "label": "WARNING / IMPAIRMENT RISK",
        "color": "#d62728",  # Red
        "description": "High probability of acute regulatory breach (DO < 4.0 mg/L). Pre-emptive interventions recommended.",
        "p_crossing_acute_min": 0.35,
        "p_crossing_acute_max": 0.70,
    },
    "EMERGENCY": {
        "level": 3,
        "label": "EMERGENCY / SEVERE HYPOXIA",
        "color": "#7b1fa2",  # Deep Purple
        "description": "Critical fish-kill / severe hypoxia hazard (DO < 2.0 mg/L or severe persistent depression). Immediate intervention required.",
        "p_crossing_acute_min": 0.70,
    },
}

# Action Window Operational Urgency Tiers (Hours to Trough)
ACTION_WINDOW_TIERS: Dict[str, Dict[str, Any]] = {
    "IMMEDIATE": {
        "max_hours": 12.0,
        "label": "Immediate Tactical Response (<12h)",
        "recommended_action": "Rapid telemetry alert; automated CSO throttling or mobile aeration deployment.",
    },
    "STANDARD": {
        "min_hours": 12.0,
        "max_hours": 24.0,
        "label": "Standard Action Window (12h - 24h)",
        "recommended_action": "Retention basin drawdown; temporary flow augmentation; targeted effluent management.",
    },
    "EXTENDED": {
        "min_hours": 24.0,
        "label": "Extended Preparation Window (>24h)",
        "recommended_action": "Watershed coordination; sustained aeration planning; downstream ecological monitoring.",
    },
}
