"""
AquaRehearsal-X - Intervention Parameters & Specifications
Stage 4: Risk-to-Action Decision Support

Defines structured configurations, validated physical ranges, operational logistics,
and peer-reviewed literature citations for four intervention archetypes:
1. Temporary In-Stream Aeration (Active Mechanical / Diffused Injection)
2. Catchment Runoff Reduction (GSI / Source Control)
3. Dynamic Stormwater & CSO Detention (Retention Basins / SCADA Gate Drawdown)
4. Riparian Buffer Canopy Shading (Thermal Buffer & Solar Interception)
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

from src.config.stage4_settings import INTERVENTION_DEFINITIONS


@dataclass
class AerationConfig:
    """Configuration for Temporary Active In-Stream Aeration."""
    oxygen_transfer_rate_mg_L_h: float = 0.04
    duration_hours: float = 24.0
    start_delay_hours: float = 4.0
    treated_reach_volume_m3: float = 2500000.0
    energy_kw_per_unit: float = 75.0

    min_prep_time_hours: float = 3.0
    implementation_time_hours: float = 1.5
    effect_lag_hours: float = 0.5

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if not (0.005 <= self.oxygen_transfer_rate_mg_L_h <= 0.25):
            errors.append(f"Oxygen transfer rate ({self.oxygen_transfer_rate_mg_L_h} mg/L/h) exceeds plausible mechanical injection bounds [0.005, 0.25].")
        if not (1.0 <= self.duration_hours <= 168.0):
            errors.append(f"Duration ({self.duration_hours} h) must be within [1, 168] hours.")
        if self.start_delay_hours < 0.0:
            errors.append(f"Start delay cannot be negative.")
        return len(errors) == 0, errors

    @property
    def total_deployment_lead_hours(self) -> float:
        """Total time required before active dissolved gas flux reaches the reach."""
        return self.min_prep_time_hours + self.implementation_time_hours + self.effect_lag_hours


@dataclass
class RunoffReductionConfig:
    """Configuration for Catchment Runoff Reduction / Source Control."""
    runoff_volume_reduction_pct: float = 20.0
    treated_catchment_fraction: float = 0.15
    bod_load_reduction_pct: float = 25.0
    inlet_cleaning_lag_hours: float = 8.0

    min_prep_time_hours: float = 6.0
    implementation_time_hours: float = 4.0
    effect_lag_hours: float = 3.0

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if not (0.0 <= self.runoff_volume_reduction_pct <= 60.0):
            errors.append(f"Runoff reduction ({self.runoff_volume_reduction_pct}%) exceeds realistic municipal infiltration capacity [0, 60%].")
        if not (0.01 <= self.treated_catchment_fraction <= 0.80):
            errors.append(f"Treated catchment fraction ({self.treated_catchment_fraction}) outside plausible bounds [0.01, 0.80].")
        if not (0.0 <= self.bod_load_reduction_pct <= 70.0):
            errors.append(f"BOD reduction ({self.bod_load_reduction_pct}%) outside plausible ranges [0, 70%].")
        return len(errors) == 0, errors

    @property
    def total_deployment_lead_hours(self) -> float:
        return self.min_prep_time_hours + self.implementation_time_hours + self.effect_lag_hours


@dataclass
class DetentionConfig:
    """Configuration for Dynamic Stormwater Retention & Real-Time CSO Detention."""
    storage_capacity_m3: float = 200000.0
    peak_attenuation_pct: float = 30.0
    controlled_release_delay_hours: float = 18.0
    overflow_threshold_rain_mm: float = 45.0

    min_prep_time_hours: float = 1.5
    implementation_time_hours: float = 0.5
    effect_lag_hours: float = 2.5

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if not (5000.0 <= self.storage_capacity_m3 <= 5000000.0):
            errors.append(f"Storage capacity ({self.storage_capacity_m3} m³) outside plausible basin sizing [5k, 5M] m³.")
        if not (5.0 <= self.peak_attenuation_pct <= 75.0):
            errors.append(f"Peak attenuation ({self.peak_attenuation_pct}%) exceeds hydraulic limits [5, 75%].")
        return len(errors) == 0, errors

    @property
    def total_deployment_lead_hours(self) -> float:
        return self.min_prep_time_hours + self.implementation_time_hours + self.effect_lag_hours


@dataclass
class RiparianShadingConfig:
    """Configuration for Riparian Buffer Canopy Shading (Thermal Buffer)."""
    canopy_shading_fraction: float = 0.40
    stream_temperature_reduction_c: float = 1.2
    upstream_reach_km: float = 15.0
    growth_maturation_years: float = 12.0

    # Long-term structural timescales
    min_prep_time_hours: float = 43800.0  # 5 years
    implementation_time_hours: float = 720.0
    effect_lag_hours: float = 1.0

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        if not (0.0 <= self.canopy_shading_fraction <= 0.95):
            errors.append(f"Canopy shading fraction ({self.canopy_shading_fraction}) outside [0, 0.95].")
        if not (0.1 <= self.stream_temperature_reduction_c <= 5.0):
            errors.append(f"Temperature reduction ({self.stream_temperature_reduction_c}°C) outside observed riparian limits [0.1, 5.0].")
        return len(errors) == 0, errors

    @property
    def total_deployment_lead_hours(self) -> float:
        return self.min_prep_time_hours + self.implementation_time_hours + self.effect_lag_hours


class InterventionParameters:
    """Master factory and registry for intervention parameters and literature sources."""

    @classmethod
    def get_default_configs(cls) -> Dict[str, Any]:
        return {
            "temporary_aeration": AerationConfig(),
            "runoff_reduction": RunoffReductionConfig(),
            "stormwater_detention": DetentionConfig(),
            "riparian_shading": RiparianShadingConfig(),
        }

    @classmethod
    def get_definitions(cls) -> Dict[str, Dict[str, Any]]:
        return INTERVENTION_DEFINITIONS

    @classmethod
    def get_citations_for(cls, intervention_key: str) -> List[str]:
        defn = INTERVENTION_DEFINITIONS.get(intervention_key, {})
        return defn.get("literature_citations", [])
