"""
AquaRehearsal-X - Stage 6 Configuration Settings
Unified One Health Decision-Support Platform & System Integration

Defines:
1. File paths for Stage 6 reports, integration artifacts, and mission control app.
2. System observability subsystems, health status codes, and criteria.
3. Historical storm replay demonstration baseline configuration.
4. Mission-control UI parameters, styling tokens, and progressive disclosure defaults.
5. Rigorous data and model provenance schemas.
"""

from pathlib import Path
from typing import Dict, Any, List

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

STAGE6_REPORTS_DIR = REPORTS_DIR / "stage6"
STAGE6_MODELS_DIR = STAGE6_REPORTS_DIR / "models"

for directory in [STAGE6_REPORTS_DIR, STAGE6_MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Upstream Artifact Directories
STAGE2_5_REPORTS_DIR = REPORTS_DIR / "stage2_5"
STAGE2_5_MODELS_DIR = STAGE2_5_REPORTS_DIR / "models"
STAGE3_REPORTS_DIR = REPORTS_DIR / "stage3"
STAGE3_MODELS_DIR = STAGE3_REPORTS_DIR / "models"
STAGE4_REPORTS_DIR = REPORTS_DIR / "stage4"
STAGE4_MODELS_DIR = STAGE4_REPORTS_DIR / "models"
STAGE5_REPORTS_DIR = REPORTS_DIR / "stage5"
STAGE5_MODELS_DIR = STAGE5_REPORTS_DIR / "models"

# Monitored Subsystems for Observability
SYSTEM_SUBSYSTEMS: List[str] = [
    "data_ingestion",
    "rainfall_integration",
    "model_forecaster",
    "forecast_generation",
    "storm_tolerance_envelope",
    "action_window_support",
    "intervention_rehearsal",
    "field_check_connectivity",
    "validation_pipeline",
]

# Standard System Health Statuses
class HealthStatus:
    AVAILABLE = "Available"
    AVAILABLE_WITH_LIMITATIONS = "Available with limitations"
    STALE = "Stale"
    UNAVAILABLE = "Unavailable"
    NOT_VALIDATED = "Not validated"

# Historical Storm Replay Demonstration Anchor (Event 54 - August 2026 Severe Summer Storm)
REPLAY_DEMO_EVENT: Dict[str, Any] = {
    "event_id": 54,
    "partition": "TEST",
    "name": "August 2026 Severe Summer Storm",
    "event_start_utc": "2026-08-05T20:00:00Z",
    "forecast_issue_utc": "2026-08-05T20:00:00Z",
    "forecast_horizon_end_utc": "2026-08-08T20:00:00Z",
    "pre_event_water_temp_c": 26.5,
    "pre_event_do_mg_l": 7.10,
    "pre_event_discharge_cfs": 900.0,
    "cumulative_rainfall_mm": 26.5,
    "rainfall_duration_hours": 10.0,
    "peak_rainfall_intensity_mm_h": 5.5,
    "peak_discharge_cfs": 4910.0,
    "peak_turbidity_fnu": 16.8,
    "observed_min_do_mg_l": 5.65,
    "observed_do_depletion_mg_l": 1.45,
    "observed_time_to_nadir_h": 10.0,
    "recovery_duration_hours": 20.0,
    "critical_threshold_mg_l": 5.0,
    "operational_risk_limit": 0.20,
    "description": (
        "Documented held-out test disturbance during peak summer thermal stress. "
        "High water temperature (26.5°C) combined with a rapid 26.5 mm rainfall surge "
        "and discharge crest of 4,910 cfs drove dissolved oxygen down by 1.45 mg/L to "
        "an acute trough of 5.65 mg/L."
    )
}

# Default Operational Parameters
DEFAULT_OPERATIONAL_CONFIG: Dict[str, Any] = {
    "station_id": "01474500",
    "station_name": "USGS 01474500 — Schuylkill River at Philadelphia, PA",
    "default_threshold_mg_L": 5.0,
    "default_risk_limit": 0.20,
    "supported_temp_min": 1.0,
    "supported_temp_max": 31.0,
    "supported_rain_min": 0.0,
    "supported_rain_max": 72.0,
}

# Scientific & Legal Disclaimers
INTEGRATION_DISCLAIMERS: Dict[str, str] = {
    "system_purpose": (
        "AquaRehearsal-X is an exploratory One Health decision-support, scenario-rehearsal, "
        "and field-verification engine. It is NOT an automated regulatory compliance tool, "
        "nor an autonomous water infrastructure control system."
    ),
    "intervention_validation": (
        "Simulated interventions (aeration, runoff reduction, detention, riparian shading) "
        "are numerical projections calculated via continuous Streeter-Phelps mass balance. "
        "They represent unvalidated exploratory scenarios and do NOT constitute measured real-world effects."
    ),
    "one_health_pathogen": (
        "Water appearance, odor, and rainfall do not directly determine pathogen concentration. "
        "Unless certified microbiological culture data (e.g., E. coli / enterococci) are present, "
        "human-contact pathogen risk must remain classified as NOT ASSESSED."
    ),
}
