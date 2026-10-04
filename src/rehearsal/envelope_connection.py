"""
AquaRehearsal-X - Storm Tolerance Envelope Connection
Stage 4: Risk-to-Action Decision Support

Connects intervention scenarios to the 2D Rainfall-vs-Temperature Storm Tolerance Envelope (STE).

Scientific Principles:
1. Physical Mapping:
   - Runoff reduction & stormwater detention attenuate effective surface rainfall (R_eff < R_base),
     shifting the operating coordinate horizontally into safer regions of the envelope.
   - Riparian shading lowers stream water temperature (T_eff < T_base), shifting the coordinate
     vertically downward (long-term structural timescale only).
   - In-stream aeration acts directly on dissolved gas concentration rather than external weather forcing.
2. Explicit Labeling:
   - Any boundary shift or risk reduction is explicitly documented as a HYPOTHETICAL SIMULATED SCENARIO.
   - Never claims that an intervention physically raises the stream's true ecological tolerance.
3. Domain Enforcement:
   - If either baseline or modified scenario lies outside the supported data domain ([1.0, 31.0]°C, [0, 72.0] mm),
     the system refuses quantitative boundary estimation with the standard refusal message.
"""

from typing import Dict, Any, Optional
import numpy as np

from src.ste.domain_support_checker import DomainSupportChecker
from src.ste.risk_model import EcologicalRiskModel
from src.config.stage4_settings import SCIENTIFIC_SAFEGUARDS
from src.rehearsal.intervention_parameters import (
    AerationConfig,
    RunoffReductionConfig,
    DetentionConfig,
    RiparianShadingConfig,
)


class EnvelopeConnector:
    """
    Evaluates scenario operating coordinates and projected risk changes
    on the 2D Storm Tolerance Envelope.
    """

    def __init__(
        self,
        risk_model: Optional[EcologicalRiskModel] = None,
        domain_checker: Optional[DomainSupportChecker] = None,
        operational_risk_limit: float = 0.20,
        default_threshold_mg_L: float = 5.0,
    ):
        self.risk_model = risk_model or EcologicalRiskModel(default_threshold_mg_L=default_threshold_mg_L)
        self.domain_checker = domain_checker or DomainSupportChecker()
        self.risk_limit = operational_risk_limit
        self.threshold = default_threshold_mg_L

    def evaluate_scenario_on_envelope(
        self,
        baseline_rain_mm: float,
        baseline_temp_c: float,
        pre_storm_do_mg_L: float,
        pre_storm_discharge_cfs: float,
        intervention_type: str,
        intervention_config: Any,
        threshold_mg_L: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculates baseline and intervention operating points on the STE surface.
        """
        thr = threshold_mg_L if threshold_mg_L is not None else self.threshold

        # 1. Domain Support Check on Baseline
        base_support = self.domain_checker.check_inputs_defensibility(
            water_temp_c=baseline_temp_c,
            storm_rain_mm=baseline_rain_mm,
            do_mg_L=pre_storm_do_mg_L,
            discharge_cfs=pre_storm_discharge_cfs,
        )

        if not base_support["is_supported"]:
            return {
                "status": "REFUSAL",
                "is_supported": False,
                "message": f"{SCIENTIFIC_SAFEGUARDS['refusal_prefix']} Baseline storm scenario is outside the supported historical data domain.",
                "reasons": base_support["reasons"],
                "baseline_operating_point": {"rain_mm": baseline_rain_mm, "temp_c": baseline_temp_c},
                "scenario_operating_point": None,
                "disclaimer": SCIENTIFIC_SAFEGUARDS["causal_disclaimer"],
            }

        # 2. Baseline Risk Estimation
        base_risk = self.risk_model.estimate_risk_probability(
            storm_rain_mm=baseline_rain_mm,
            pre_storm_water_temp_c=baseline_temp_c,
            pre_storm_do_mg_L=pre_storm_do_mg_L,
            pre_storm_discharge_cfs=pre_storm_discharge_cfs,
            threshold_mg_L=thr,
        )

        # 3. Derive Scenario Modified Operating Coordinate
        mod_rain = baseline_rain_mm
        mod_temp = baseline_temp_c
        mod_do = pre_storm_do_mg_L
        shift_mechanism = "None"

        if intervention_type == "runoff_reduction" and isinstance(intervention_config, RunoffReductionConfig):
            attenuation = (intervention_config.runoff_volume_reduction_pct / 100.0) * intervention_config.treated_catchment_fraction
            mod_rain = max(0.0, baseline_rain_mm * (1.0 - attenuation))
            shift_mechanism = f"Catchment infiltration reduces effective runoff depth by {attenuation * 100.0:.1f}% (horizontal leftward shift)."

        elif intervention_type == "stormwater_detention" and isinstance(intervention_config, DetentionConfig):
            if baseline_rain_mm > intervention_config.overflow_threshold_rain_mm:
                bypass = (baseline_rain_mm - intervention_config.overflow_threshold_rain_mm) / baseline_rain_mm
                attenuation = (intervention_config.peak_attenuation_pct / 100.0) * (1.0 - bypass)
            else:
                attenuation = intervention_config.peak_attenuation_pct / 100.0
            mod_rain = max(0.0, baseline_rain_mm * (1.0 - attenuation))
            shift_mechanism = f"Detention chamber peak-shaving attenuates effective rainfall by {attenuation * 100.0:.1f}% (horizontal leftward shift)."

        elif intervention_type == "riparian_shading" and isinstance(intervention_config, RiparianShadingConfig):
            mod_temp = max(1.0, baseline_temp_c - intervention_config.stream_temperature_reduction_c)
            shift_mechanism = f"Canopy shading moderates water temperature by {intervention_config.stream_temperature_reduction_c:.1f}°C (vertical downward shift; multi-year timescale)."

        elif intervention_type == "temporary_aeration" and isinstance(intervention_config, AerationConfig):
            # Aeration does not alter weather forcing; it provides active dissolved oxygen flux
            total_o2_added = intervention_config.oxygen_transfer_rate_mg_L_h * min(24.0, intervention_config.duration_hours)
            mod_do = min(14.0, pre_storm_do_mg_L + total_o2_added * 0.50)  # Effective assimilative margin increase
            shift_mechanism = f"Mechanical aeration directly elevates dissolved gas concentration by ~{total_o2_added * 0.50:.2f} mg/L, increasing assimilative margin without changing weather coordinates."

        # 4. Domain Check on Modified Operating Point
        mod_support = self.domain_checker.check_inputs_defensibility(
            water_temp_c=mod_temp,
            storm_rain_mm=mod_rain,
            do_mg_L=mod_do,
            discharge_cfs=pre_storm_discharge_cfs,
        )

        if not mod_support["is_supported"]:
            return {
                "status": "PARTIAL_SUPPORT",
                "is_supported": False,
                "message": f"{SCIENTIFIC_SAFEGUARDS['refusal_prefix']} Modified scenario coordinate exceeds supported domain bounds.",
                "reasons": mod_support["reasons"],
                "baseline_operating_point": {"rain_mm": baseline_rain_mm, "temp_c": baseline_temp_c, "risk_prob": round(base_risk, 4)},
                "scenario_operating_point": {"rain_mm": mod_rain, "temp_c": mod_temp},
                "disclaimer": SCIENTIFIC_SAFEGUARDS["causal_disclaimer"],
            }

        # 5. Modified Risk Estimation
        mod_risk = self.risk_model.estimate_risk_probability(
            storm_rain_mm=mod_rain,
            pre_storm_water_temp_c=mod_temp,
            pre_storm_do_mg_L=mod_do,
            pre_storm_discharge_cfs=pre_storm_discharge_cfs,
            threshold_mg_L=thr,
        )

        risk_reduction = base_risk - mod_risk

        return {
            "status": "VALID_MAPPING",
            "is_supported": True,
            "threshold_mg_L": thr,
            "operational_risk_limit": self.risk_limit,
            "baseline": {
                "rainfall_mm": round(baseline_rain_mm, 1),
                "water_temperature_c": round(baseline_temp_c, 1),
                "estimated_risk_probability": round(base_risk, 4),
                "in_elevated_risk_zone": bool(base_risk >= self.risk_limit),
            },
            "scenario": {
                "intervention_type": intervention_type,
                "rainfall_mm": round(mod_rain, 1),
                "water_temperature_c": round(mod_temp, 1),
                "estimated_risk_probability": round(mod_risk, 4),
                "in_elevated_risk_zone": bool(mod_risk >= self.risk_limit),
                "risk_probability_reduction": round(max(0.0, risk_reduction), 4),
                "shift_mechanism": shift_mechanism,
            },
            "scientific_label": "Hypothetical Scenario Mapping (Simulated Shift, Not Measured Reality)",
            "disclaimer": SCIENTIFIC_SAFEGUARDS["causal_disclaimer"],
        }
