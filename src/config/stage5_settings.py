"""
AquaRehearsal-X - Stage 5 Configuration Settings
Citizen Observation and Prediction Verification System (Field Check)

Defines:
1. Spatial bounding boxes, monitoring site coordinates, and matching thresholds.
2. Standardized controlled vocabularies for visual observations and field measurements.
3. Review states and audit trail definitions.
4. One Health categorical boundaries and public health safety disclaimers.
5. Privacy controls and coordinate coarsening parameters.
"""

from pathlib import Path
from typing import Dict, Any, List

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

STAGE5_REPORTS_DIR = REPORTS_DIR / "stage5"
STAGE5_MODELS_DIR = STAGE5_REPORTS_DIR / "models"
STAGE5_UPLOADS_DIR = STAGE5_REPORTS_DIR / "uploads"

for directory in [STAGE5_REPORTS_DIR, STAGE5_MODELS_DIR, STAGE5_UPLOADS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Station Reference Coordinates (USGS 01474500, Schuylkill River at Philadelphia)
STATION_COORDINATES: Dict[str, float] = {
    "latitude": 39.96779,
    "longitude": -75.18850,
}

# Schuylkill River Watershed Bounding Box (Plausible observation area)
SCHUYLKILL_BOUNDS: Dict[str, float] = {
    "min_latitude": 39.8500,
    "max_latitude": 40.6000,
    "min_longitude": -76.2000,
    "max_longitude": -75.0500,
}

# Spatial and Temporal Matching Tolerances
SPATIAL_MATCHING_RADIUS_KM: float = 20.0  # Max distance along reach to match predictions
DIRECT_GAGE_RADIUS_KM: float = 3.0       # Distance for direct gage proximity
TEMPORAL_MATCHING_WINDOW_HOURS: float = 36.0  # Max time difference between forecast & observation

# Physical Measurement Valid Ranges
MEASUREMENT_BOUNDS: Dict[str, Dict[str, Any]] = {
    "dissolved_oxygen_mg_L": {
        "min": 0.0,
        "max": 20.0,
        "unit": "mg/L",
        "description": "Handheld probe or field titration dissolved oxygen concentration.",
    },
    "water_temperature_c": {
        "min": -2.0,
        "max": 38.0,
        "unit": "°C",
        "description": "Stream water temperature at time of field observation.",
    },
    "ph": {
        "min": 3.0,
        "max": 11.5,
        "unit": "pH units",
        "description": "Stream acidity / alkalinity measured via probe or strip.",
    },
    "specific_conductance_us_cm": {
        "min": 10.0,
        "max": 8000.0,
        "unit": "μS/cm",
        "description": "Conductivity indicator of dissolved ionic solids.",
    },
}

# Controlled Vocabularies
OBSERVATION_VOCABULARY: Dict[str, List[str]] = {
    "water_appearance": [
        "clear",
        "slightly_cloudy",
        "turbid_muddy",
        "green_algal",
        "oily_sheen",
        "dark_tea_colored",
        "other",
    ],
    "unusual_foam": [
        "none",
        "light_flecks",
        "moderate_patches",
        "dense_persistent_suds",
    ],
    "unusual_odor": [
        "none",
        "earthy_musty",
        "sewage_cso",
        "petroleum_fuel",
        "rotten_egg_sulfur",
        "chemical",
        "decaying_organic",
        "other",
    ],
    "aquatic_life_status": [
        "none_observed",
        "normal_active_fish",
        "fish_piping_surface",
        "dead_fish_few_1_5",
        "dead_fish_moderate_6_20",
        "dead_fish_large_kill_over_20",
        "dead_macroinvertebrates",
        "abundant_macroinvertebrates",
        "other_wildlife",
    ],
    "visible_discoloration": [
        "none",
        "brown_sediment",
        "reddish_brown",
        "bright_green_bloom",
        "milky_white",
        "black_anaerobic",
        "other",
    ],
    "recent_weather": [
        "dry_clear",
        "light_intermittent_rain",
        "heavy_downpour",
        "recent_storm_runoff",
        "prolonged_dry_spell",
    ],
}

# Review Workflow States
REVIEW_STATES: List[str] = [
    "PENDING_REVIEW",
    "VERIFIED",
    "NEEDS_CONFIRMATION",
    "INCOMPLETE",
    "REJECTED",
    "DUPLICATE",
]

# Forecast Corroboration Categories
CORROBORATION_STATUSES: List[str] = [
    "CORROBORATES_PREDICTED_RISK",
    "CORROBORATES_PREDICTED_SAFE",
    "CONTRADICTS_PREDICTED_RISK",
    "CONTRADICTS_PREDICTED_SAFE",
    "INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
]

# Privacy Settings
PRIVACY_CONFIG: Dict[str, Any] = {
    "coarsen_coordinates_decimals": 2,  # ~1.1 km precision for public display
    "strip_exif_metadata": True,
    "allow_anonymous_reports": True,
    "max_image_size_bytes": 10 * 1024 * 1024,  # 10 MB
    "allowed_image_mimes": ["image/jpeg", "image/png", "image/webp"],
}

# One Health Disclaimers & Categories
ONE_HEALTH_CATEGORIES: Dict[str, Dict[str, str]] = {
    "environmental": {
        "title": "Environmental & Hydrological Conditions",
        "description": "Physical stream parameters, runoff dynamics, storm timing, and dissolved oxygen concentrations.",
    },
    "aquatic_life": {
        "title": "Aquatic Wildlife & Ecological Welfare",
        "description": "Observed fish behavior, benthic macroinvertebrate presence, surface piping, and mortality signals.",
    },
    "human_contact": {
        "title": "Human Recreational Contact & Precautionary Guidance",
        "description": "General non-potable water precautions during wet weather. Does NOT constitute medical advice.",
    },
}

STAGE5_DISCLAIMERS: Dict[str, str] = {
    "general_disclaimer": (
        "AquaRehearsal-X Field Check is a citizen-science observation and model-verification platform, "
        "NOT a substitute for laboratory environmental testing or certified municipal water quality enforcement."
    ),
    "health_disclaimer": (
        "Human recreational contact risk has NOT been laboratory-assessed unless official certified bacteriological "
        "measurements (e.g. E. coli / enterococci) or municipal health department advisories are explicitly cited. "
        "Do NOT infer pathogen levels from water appearance, foam, or odor alone. Never enter floodwaters."
    ),
    "unverified_notice": (
        "Unverified field submissions represent subjective citizen observations and have not yet undergone "
        "professional QA/QC verification."
    ),
}
