"""
AquaRehearsal-X - Stage 3 Programmatic STE & Early-Warning API Interface
Storm Tolerance Envelope (STE), Dynamic Conditioning & Action-Window Services

Provides a clean, typed programmatic endpoint for evaluating the resilience boundary,
expected DO nadir, boundary-crossing probabilities, and actionable intervention windows
for any given current river state and incoming weather forecast.

Usage:
    from src.models.ste_api import evaluate_storm_tolerance

    result = evaluate_storm_tolerance(
        current_conditions={
            "water_temperature": 24.5,
            "dissolved_oxygen": 7.8,
            "discharge": 1150.0,
            "antecedent_rain_72h": 12.0,
        },
        incoming_storm_forecast={
            "storm_rain_mm": 28.0,
            "discharge_surge_ratio": 3.8,
            "storm_duration_hours": 14.0,
        }
    )
"""

from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import json
import numpy as np
import pandas as pd

from src.config.stage3_settings import (
    STAGE3_REGULATORY_THRESHOLDS,
    STAGE3_MODELS_DIR,
    STAGE2_5_MODELS_DIR,
)
from src.ste.envelope_engine import StormToleranceEnvelope, calculate_benson_krause_saturation
from src.ste.probability_engine import BoundaryCrossingProbability, StratifiedUncertaintyCalibrator
from src.ste.action_window import ActionWindowEstimator
from src.models.ood_checker import InputDomainChecker
from src.utils.logger import logger


class StormToleranceAPI:
    """Encapsulates Stage 3 STE engines and provides unified inference API."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir or STAGE3_MODELS_DIR)
        self.ste_engine = StormToleranceEnvelope()
        self.calibrator = StratifiedUncertaintyCalibrator.load(self.models_dir / "stage3_stratified_uncertainty.json")
        self.prob_engine = BoundaryCrossingProbability(calibrator=self.calibrator)
        self.window_estimator = ActionWindowEstimator()
        
        # Load OOD domain checker from Stage 2.5
        domain_path = STAGE2_5_MODELS_DIR / "domain_ranges_stage2_5.json"
        self.domain_checker = InputDomainChecker.load(domain_path) if domain_path.exists() else None

    def evaluate(
        self,
        current_conditions: Dict[str, float],
        incoming_storm_forecast: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates the Storm Tolerance Envelope and early-warning diagnostics.
        """
        temp_c = float(current_conditions.get("water_temperature", current_conditions.get("temp", 18.0)))
        do_base = float(current_conditions.get("dissolved_oxygen", current_conditions.get("do", 8.0)))
        q_base = float(current_conditions.get("discharge", current_conditions.get("q", 1200.0)))
        api_72h = float(current_conditions.get("antecedent_rain_72h", current_conditions.get("api_72h", 0.0)))

        forecast = incoming_storm_forecast or {}
        storm_rain = float(forecast.get("storm_rain_mm", forecast.get("rain_mm", 0.0)))
        surge_ratio = float(forecast.get("discharge_surge_ratio", forecast.get("surge_ratio", 1.0)))
        duration_hours = float(forecast.get("storm_duration_hours", forecast.get("duration_hours", 12.0)))

        # 1. Storm Tolerance Envelope Evaluation
        ste_eval = self.ste_engine.evaluate_envelope(
            ambient_temp_c=temp_c,
            ambient_do_mg_L=do_base,
            ambient_discharge_cfs=q_base,
            incoming_rain_mm=storm_rain,
            incoming_discharge_surge_ratio=surge_ratio,
            antecedent_rain_72h_mm=api_72h,
        )
        expected_min_do = ste_eval["expected_minimum_do_mg_L"]

        # 2. Thermally Conditioned Uncertainty & Crossing Probabilities
        probs = self.prob_engine.compute_crossing_probabilities(expected_min_do, temp_c)
        int_low, int_high = self.prob_engine.compute_prediction_interval(expected_min_do, temp_c)
        alert_info = self.prob_engine.determine_alert_level(
            expected_min_do=expected_min_do,
            p_acute_4_0=probs["p_crossing_acute_4_0"],
            p_hypoxia_2_0=probs["p_crossing_hypoxia_2_0"],
        )

        # 3. Time-to-Trough & Operational Action Window
        pred_lag = self.window_estimator.estimate_time_to_trough(
            storm_duration_hours=duration_hours,
            discharge_surge_ratio=surge_ratio,
            water_temperature_c=temp_c,
            storm_rainfall_mm=storm_rain,
        )
        window_info = self.window_estimator.characterize_action_window(pred_lag)

        # 4. Out-of-Distribution Warning Check
        ood_result = {"has_domain_warning": False, "warnings": []}
        if self.domain_checker:
            sample_features = {
                "water_temperature": temp_c,
                "dissolved_oxygen": do_base,
                "discharge": q_base,
                "rain_mm": storm_rain,
            }
            ood_result = self.domain_checker.check_sample(sample_features)

        return {
            "service": "AquaRehearsal-X Storm Tolerance & Early-Warning API",
            "regulatory_framework": "Pennsylvania Code Title 25 Chapter 93 (Warm Water Fishes Criteria)",
            "alert_status": {
                "level": alert_info["level"],
                "key": alert_info["key"],
                "label": alert_info["label"],
                "color": alert_info["color"],
                "description": alert_info["description"],
            },
            "tolerance_envelope": {
                "expected_minimum_do_72h_mg_L": expected_min_do,
                "prediction_interval_80": [int_low, int_high],
                "remaining_assimilative_capacity_pct": ste_eval["remaining_assimilative_capacity_pct"],
                "critical_rainfall_standard_5_0_mm": ste_eval["critical_rainfall_standard_5_0_mm"],
                "critical_rainfall_acute_4_0_mm": ste_eval["critical_rainfall_acute_4_0_mm"],
                "critical_rainfall_hypoxia_2_0_mm": ste_eval["critical_rainfall_hypoxia_2_0_mm"],
                "critical_discharge_surge_ratio_4_0": ste_eval["critical_discharge_surge_ratio_4_0"],
                "buffer_standard_5_0_mg_L": ste_eval["buffer_standard_5_0_mg_L"],
                "buffer_acute_4_0_mg_L": ste_eval["buffer_acute_4_0_mg_L"],
            },
            "boundary_crossing_probabilities": {
                "p_crossing_standard_5_0": probs["p_crossing_standard_5_0"],
                "p_crossing_acute_4_0": probs["p_crossing_acute_4_0"],
                "p_crossing_hypoxia_2_0": probs["p_crossing_hypoxia_2_0"],
                "effective_dispersion_sigma": probs["effective_dispersion_sigma"],
            },
            "action_window": {
                "estimated_time_to_trough_hours": window_info["estimated_time_to_trough_hours"],
                "actionable_window_hours": window_info["actionable_window_hours"],
                "urgency_tier": window_info["urgency_tier"],
                "urgency_label": window_info["urgency_label"],
                "recommended_operational_action": window_info["recommended_operational_action"],
            },
            "conditioning_context": {
                "thermal_tier": ste_eval["thermal_tier"],
                "antecedent_moisture_tier": ste_eval["antecedent_moisture_tier"],
                "saturation_do_mg_L": ste_eval["saturation_do_mg_L"],
                "incoming_storm_rain_mm": storm_rain,
                "incoming_discharge_surge_ratio": surge_ratio,
            },
            "domain_warning": ood_result,
        }


# Singleton instance for high-performance direct import
_api_instance: Optional[StormToleranceAPI] = None


def get_ste_api() -> StormToleranceAPI:
    """Returns singleton instance of StormToleranceAPI."""
    global _api_instance
    if _api_instance is None:
        _api_instance = StormToleranceAPI()
    return _api_instance


def evaluate_storm_tolerance(
    current_conditions: Dict[str, float],
    incoming_storm_forecast: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Public top-level function to evaluate stream tolerance and early warning.
    """
    api = get_ste_api()
    return api.evaluate(current_conditions, incoming_storm_forecast)
