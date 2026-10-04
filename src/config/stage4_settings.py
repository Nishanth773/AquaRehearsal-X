"""
AquaRehearsal-X - Stage 4 Configuration Settings
Action Window & Intervention Rehearsal Engine (Risk-to-Action Decision Support)

Defines:
1. Directory paths for Stage 4 deliverables, models, and visual artifacts.
2. Action window time horizon intervals (6, 12, 24, 48, 72 hours).
3. Peer-reviewed parameter bounds and operational constraints for 4 intervention archetypes:
   - Temporary Mechanical / Diffused Aeration
   - Catchment Runoff Reduction / Source Control
   - Stormwater Retention / Real-Time CSO Detention
   - Riparian Canopy Shading (Thermal Buffer)
4. Feasibility tier criteria and logistical latency thresholds.
5. Standardized refusal declarations and scientific safety disclaimers.
"""

from pathlib import Path
from typing import Dict, Any, List

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

STAGE3_REPORTS_DIR = REPORTS_DIR / "stage3"
STAGE3_MODELS_DIR = STAGE3_REPORTS_DIR / "models"

STAGE4_REPORTS_DIR = REPORTS_DIR / "stage4"
STAGE4_MODELS_DIR = STAGE4_REPORTS_DIR / "models"
STAGE4_PLOTS_DIR = STAGE4_REPORTS_DIR

# Ensure Stage 4 directories exist
for directory in [STAGE4_REPORTS_DIR, STAGE4_MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Station and Input Datasets
STAGE4_DATA_CONFIG: Dict[str, Any] = {
    "station_id": "01474500",
    "station_name": "Schuylkill River at Philadelphia, PA",
    "extended_data_file": "station_01474500_extended_1h.csv",
    "historical_events_file": "historical_storm_events.csv",
    "stage3_replay_file": "historical_storm_replay.csv",
    "stage3_metadata_file": "stage3_metadata.json",
    "temporal_resolution": "1h",
    "drainage_area_sq_mi": 1893.0,
    "simulation_horizon_hours": 72,
    "time_step_hours": 1.0,
    "random_seed": 42,
}

# Action Window Evaluation Horizons (hours)
ACTION_WINDOW_HORIZONS: List[int] = [6, 12, 24, 48, 72]

# Operational Feasibility Classifications
FEASIBILITY_TIERS: Dict[str, Dict[str, str]] = {
    "POTENTIALLY_FEASIBLE": {
        "label": "Potentially Feasible within Action Window",
        "description": "Total deployment latency (prep + implementation + effect lag) is shorter than the estimated earliest threshold crossing time. The intervention can physically exert an environmental effect before the DO trough.",
        "badge_color": "#10b981",
    },
    "FEASIBILITY_UNCERTAIN": {
        "label": "Feasibility Uncertain / Borderline",
        "description": "Total required deployment time falls near or slightly exceeds the earliest estimated crossing time, but remains within the median crossing window. Success depends heavily on pre-storm mobilization readiness.",
        "badge_color": "#f59e0b",
    },
    "UNLIKELY_TO_AFFECT": {
        "label": "Unlikely to Affect Current Event",
        "description": "Deployment time or environmental response lag exceeds the 72-hour disturbance window, or the intervention is a long-term structural/ecological change requiring weeks to decades.",
        "badge_color": "#ef4444",
    },
    "INSUFFICIENT_EVIDENCE": {
        "label": "Insufficient Evidence to Assess",
        "description": "Crucial sensory inputs, hydraulic conditions, or operational parameters are missing, stale, or out of physical bounds.",
        "badge_color": "#6b7280",
    },
}

# Peer-Reviewed Literature Parameterizations for Intervention Archetypes
INTERVENTION_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "temporary_aeration": {
        "name": "Temporary Active Aeration",
        "category": "Active In-Stream Mechanical Injection",
        "mechanism": "Mechanical surface aerators, draft tubes, or micro-bubble oxygen injection barges deployed directly into targeted river reaches to increase dissolved gas transfer.",
        "parameters": {
            "oxygen_transfer_rate_mg_L_h": {
                "default": 0.04,
                "min": 0.01,
                "max": 0.12,
                "unit": "mg DO / (L · h)",
                "description": "Volumetric dissolved oxygen transfer rate delivered to the reach.",
            },
            "duration_hours": {
                "default": 24.0,
                "min": 4.0,
                "max": 72.0,
                "unit": "hours",
                "description": "Continuous operating duration of the aeration system.",
            },
            "start_delay_hours": {
                "default": 4.0,
                "min": 0.0,
                "max": 48.0,
                "unit": "hours after forecast issue",
                "description": "Scheduled startup time after alert trigger.",
            },
            "treated_reach_volume_m3": {
                "default": 2500000.0,
                "min": 500000.0,
                "max": 10000000.0,
                "unit": "m³",
                "description": "Effective channel water volume under active aeration influence.",
            },
            "energy_kw_per_unit": {
                "default": 75.0,
                "min": 25.0,
                "max": 250.0,
                "unit": "kW",
                "description": "Power demand per aeration unit.",
            },
        },
        "logistics": {
            "min_prep_time_hours": 3.0,
            "typical_prep_time_hours": 5.0,
            "implementation_time_hours": 1.5,
            "effect_lag_hours": 0.5,
            "total_minimum_lead_hours": 5.0,
        },
        "literature_citations": [
            "Alabaster, J. S. (1988). The use of artificial aeration in the management of dissolved oxygen in the Thames Estuary. Water Research, 22(8), 983-989.",
            "Suszek, F., & Ziemnicka, M. (2018). Mobile and emergency aeration systems for urban water bodies under hypoxic stress. Ecological Engineering, 117, 45-53.",
            "US EPA (2002). Wastewater Technology Fact Sheet: Fine Bubble Aeration. EPA 832-F-02-005.",
        ],
    },
    "runoff_reduction": {
        "name": "Catchment Runoff Reduction",
        "category": "Catchment Source Control & Green Stormwater Infrastructure (GSI)",
        "mechanism": "Pre-storm permeable surface clearing, bioretention drawdown, and distributed catchment infiltration reducing urban wash-off volume and initial organic particulate loading.",
        "parameters": {
            "runoff_volume_reduction_pct": {
                "default": 20.0,
                "min": 5.0,
                "max": 45.0,
                "unit": "%",
                "description": "Hypothetical percentage reduction in effective storm surface runoff volume.",
            },
            "treated_catchment_fraction": {
                "default": 0.15,
                "min": 0.02,
                "max": 0.40,
                "unit": "dimensionless (0-1)",
                "description": "Fraction of urban impervious watershed draining to active retention.",
            },
            "bod_load_reduction_pct": {
                "default": 25.0,
                "min": 5.0,
                "max": 50.0,
                "unit": "%",
                "description": "Estimated reduction in carbonaceous biochemical oxygen demand (CBOD).",
            },
            "inlet_cleaning_lag_hours": {
                "default": 8.0,
                "min": 2.0,
                "max": 36.0,
                "unit": "hours",
                "description": "Mobilization time for pre-storm vacuum sweeping and inlet clearage.",
            },
        },
        "logistics": {
            "min_prep_time_hours": 6.0,
            "typical_prep_time_hours": 12.0,
            "implementation_time_hours": 4.0,
            "effect_lag_hours": 3.0,
            "total_minimum_lead_hours": 13.0,
        },
        "literature_citations": [
            "Dietz, M. E. (2007). Low impact development practices: A review of current research and recommendations for future directions. Water, Air, and Soil Pollution, 186(1), 351-363.",
            "US EPA (2015). Green Infrastructure for Stormwater Management: Cost-Benefit Analysis and Water Quality Benefits. EPA 841-R-15-001.",
            "Philadelphia Water Department (2020). Green City, Clean Waters 10-Year Evaluation Report. Philadelphia, PA.",
        ],
    },
    "stormwater_detention": {
        "name": "Dynamic Stormwater & CSO Detention",
        "category": "Real-Time Hydraulic Storage & Peak Shaving",
        "mechanism": "Pre-storm drawdown of offline storage tunnels and wet retention basins, paired with automated SCADA gate throttling to attenuate peak runoff and delay organic load delivery.",
        "parameters": {
            "storage_capacity_m3": {
                "default": 200000.0,
                "min": 25000.0,
                "max": 1000000.0,
                "unit": "m³",
                "description": "Total available active storage capacity in retention chambers / tunnels.",
            },
            "peak_attenuation_pct": {
                "default": 30.0,
                "min": 10.0,
                "max": 60.0,
                "unit": "%",
                "description": "Reduction in hydrograph peak discharge rate during storm crest.",
            },
            "controlled_release_delay_hours": {
                "default": 18.0,
                "min": 6.0,
                "max": 48.0,
                "unit": "hours",
                "description": "Duration detained stormwater is held before staged dry-weather release.",
            },
            "overflow_threshold_rain_mm": {
                "default": 45.0,
                "min": 25.0,
                "max": 70.0,
                "unit": "mm",
                "description": "Storm precipitation depth beyond which basin storage capacity is exceeded.",
            },
        },
        "logistics": {
            "min_prep_time_hours": 1.5,
            "typical_prep_time_hours": 3.0,
            "implementation_time_hours": 0.5,
            "effect_lag_hours": 2.5,
            "total_minimum_lead_hours": 4.5,
        },
        "literature_citations": [
            "Stovin, V. R., & Saul, A. J. (1998). A review of the efficiency of storage chambers for combined sewer overflow control. Water Science and Technology, 37(1), 147-154.",
            "Dirckx, G., et al. (2011). Real-time control of sewer systems: A multi-objective optimization approach for urban drainage. Journal of Hydroinformatics, 13(4), 629-644.",
            "PWD (2018). Long Term Control Plan Update: Combined Sewer System Hydraulics. Philadelphia Water Dept.",
        ],
    },
    "riparian_shading": {
        "name": "Riparian Buffer Canopy Shading",
        "category": "Structural Catchment Restoration & Thermal Shielding",
        "mechanism": "Mature deciduous and coniferous riparian forest canopy along upstream tributary corridors, attenuating solar thermal radiation and moderating stream temperatures.",
        "parameters": {
            "canopy_shading_fraction": {
                "default": 0.40,
                "min": 0.10,
                "max": 0.85,
                "unit": "fraction (0-1)",
                "description": "Fraction of incident solar shortwave radiation intercepted by vegetation.",
            },
            "stream_temperature_reduction_c": {
                "default": 1.2,
                "min": 0.2,
                "max": 3.0,
                "unit": "°C",
                "description": "Estimated reduction in summertime daily peak water temperature.",
            },
            "upstream_reach_km": {
                "default": 15.0,
                "min": 2.0,
                "max": 50.0,
                "unit": "km",
                "description": "Length of reforested riparian corridor upstream of monitoring station.",
            },
            "growth_maturation_years": {
                "default": 12.0,
                "min": 5.0,
                "max": 25.0,
                "unit": "years",
                "description": "Timescale required for planted saplings to reach effective shading height.",
            },
        },
        "logistics": {
            "min_prep_time_hours": 43800.0,  # ~5 years in hours
            "typical_prep_time_hours": 87600.0,  # ~10 years
            "implementation_time_hours": 720.0,
            "effect_lag_hours": 1.0,
            "total_minimum_lead_hours": 44520.0,  # Long-term structural
        },
        "literature_citations": [
            "Broadmeadow, S., & Nisbet, T. R. (2004). The effects of riparian forest management on the fine sediment dynamics of aquatic ecosystems. Hydrological Processes, 18(17), 3255-3272.",
            "Garner, G., et al. (2017). The role of riparian shading in buffering stream temperatures across diverse UK landscapes. Hydrological Processes, 31(17), 2995-3007.",
            "Moore, R. D., et al. (2005). Riparian microclimate and stream temperature and their response to forest harvesting: A review. Journal of the American Water Resources Association, 41(4), 813-834.",
        ],
    },
}

# Standardized Refusal & Safety Declarations
SCIENTIFIC_SAFEGUARDS: Dict[str, str] = {
    "refusal_prefix": "Insufficient evidence to estimate this scenario reliably.",
    "causal_disclaimer": "Simulated intervention outcomes represent exploratory scenario rehearsals based on idealized mass-balance kinetics and do NOT constitute measured real-world treatment effects.",
    "action_window_disclaimer": "The action window represents an empirical statistical estimate of potential response latency based on historical storm nadir timings, NOT an exact countdown or a physical guarantee of safety.",
    "uncalibrated_disclaimer": "Simulations are derived from generalized Streeter-Phelps oxygen transfer equations. Because no controlled in-situ field aeration trials were performed at USGS 01474500 during 2023-2026, absolute quantitative outcomes have NOT been empirically validated against real-world stream treatment experiments.",
    "ranking_rule": "Interventions are presented side-by-side with distinct operational, energy, and logistical constraints. The system explicitly refrains from automated single-metric ranking or winner selection.",
}
