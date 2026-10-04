"""
AquaRehearsal-X - Scenario Rehearsal Runner
Stage 4: Risk-to-Action Decision Support

Master orchestrator for running multi-intervention rehearsals under incoming storm conditions.
Coordinates Action Window Estimation, Oxygen Balance Simulation, Feasibility Filtering,
and Storm Tolerance Envelope Mapping.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from src.rehearsal.action_window_estimator import ActionWindowEstimator
from src.rehearsal.oxygen_balance_model import OxygenBalanceModel
from src.rehearsal.feasibility_filter import FeasibilityFilter
from src.rehearsal.envelope_connection import EnvelopeConnector
from src.rehearsal.intervention_parameters import (
    InterventionParameters,
    AerationConfig,
    RunoffReductionConfig,
    DetentionConfig,
    RiparianShadingConfig,
)
from src.ste.domain_support_checker import DomainSupportChecker
from src.ste.risk_model import EcologicalRiskModel
from src.config.stage4_settings import SCIENTIFIC_SAFEGUARDS
from src.utils.logger import logger


class ScenarioRunner:
    """
    Executes baseline and intervention scenario rehearsals for any specified storm event.
    """

    def __init__(
        self,
        default_threshold_mg_L: float = 5.0,
        operational_risk_limit: float = 0.20,
        risk_model: Optional[EcologicalRiskModel] = None,
        domain_checker: Optional[DomainSupportChecker] = None,
    ):
        self.threshold = default_threshold_mg_L
        self.risk_limit = operational_risk_limit

        self.risk_model = risk_model or EcologicalRiskModel(default_threshold_mg_L=default_threshold_mg_L)
        self.domain_checker = domain_checker or DomainSupportChecker()

        self.window_estimator = ActionWindowEstimator(default_threshold_mg_L=default_threshold_mg_L)
        self.oxygen_model = OxygenBalanceModel()
        self.feasibility_filter = FeasibilityFilter()
        self.envelope_connector = EnvelopeConnector(
            risk_model=self.risk_model,
            domain_checker=self.domain_checker,
            operational_risk_limit=operational_risk_limit,
            default_threshold_mg_L=default_threshold_mg_L,
        )

    def rehearse_all_scenarios(
        self,
        pre_storm_water_temp_c: float,
        pre_storm_do_mg_L: float,
        pre_storm_discharge_cfs: float,
        storm_rain_mm: float,
        storm_duration_hours: float = 18.0,
        custom_configs: Optional[Dict[str, Any]] = None,
        threshold_mg_L: Optional[float] = None,
        scenario_label: str = "Hypothetical Storm Scenario",
    ) -> Dict[str, Any]:
        """
        Runs complete rehearsal across all 4 intervention archetypes alongside baseline.
        """
        thr = threshold_mg_L if threshold_mg_L is not None else self.threshold

        # 1. Domain Support Check
        support_check = self.domain_checker.check_inputs_defensibility(
            water_temp_c=pre_storm_water_temp_c,
            storm_rain_mm=storm_rain_mm,
            do_mg_L=pre_storm_do_mg_L,
            discharge_cfs=pre_storm_discharge_cfs,
        )

        if not support_check["is_supported"]:
            return {
                "status": "REFUSAL",
                "is_supported": False,
                "scenario_label": scenario_label,
                "message": f"{SCIENTIFIC_SAFEGUARDS['refusal_prefix']} Inputs fall outside the supported historical domain.",
                "reasons": support_check["reasons"],
                "disclaimer": SCIENTIFIC_SAFEGUARDS["causal_disclaimer"],
            }

        # 2. Risk Model 72h Probability
        p_breach_72h = self.risk_model.estimate_risk_probability(
            storm_rain_mm=storm_rain_mm,
            pre_storm_water_temp_c=pre_storm_water_temp_c,
            pre_storm_do_mg_L=pre_storm_do_mg_L,
            pre_storm_discharge_cfs=pre_storm_discharge_cfs,
            threshold_mg_L=thr,
        )

        # 3. Action Window Estimation
        action_window = self.window_estimator.estimate_action_window(
            pre_storm_water_temp_c=pre_storm_water_temp_c,
            pre_storm_do_mg_L=pre_storm_do_mg_L,
            pre_storm_discharge_cfs=pre_storm_discharge_cfs,
            storm_rain_mm=storm_rain_mm,
            storm_duration_hours=storm_duration_hours,
            threshold_mg_L=thr,
            prob_72h_crossing=p_breach_72h,
        )

        # 4. Baseline Oxygen Balance Simulation
        base_sim = self.oxygen_model.simulate_trajectory(
            pre_storm_water_temp_c=pre_storm_water_temp_c,
            pre_storm_do_mg_L=pre_storm_do_mg_L,
            pre_storm_discharge_cfs=pre_storm_discharge_cfs,
            storm_rain_mm=storm_rain_mm,
            storm_duration_hours=storm_duration_hours,
            intervention_type=None,
        )

        base_min_do = base_sim["minimum_do_mg_L"]

        # 5. Rehearse Each of the 4 Interventions
        configs = custom_configs or InterventionParameters.get_default_configs()
        scenarios_results = {}

        for itype in ["temporary_aeration", "runoff_reduction", "stormwater_detention", "riparian_shading"]:
            cfg = configs.get(itype, InterventionParameters.get_default_configs()[itype])

            # Oxygen balance simulation
            sim_res = self.oxygen_model.simulate_trajectory(
                pre_storm_water_temp_c=pre_storm_water_temp_c,
                pre_storm_do_mg_L=pre_storm_do_mg_L,
                pre_storm_discharge_cfs=pre_storm_discharge_cfs,
                storm_rain_mm=storm_rain_mm,
                storm_duration_hours=storm_duration_hours,
                intervention_type=itype,
                intervention_config=cfg,
            )

            mod_min_do = sim_res["minimum_do_mg_L"]
            do_gain = round(mod_min_do - base_min_do, 2)

            # Feasibility Filter
            feas_res = self.feasibility_filter.evaluate_feasibility(
                intervention_type=itype,
                intervention_config=cfg,
                action_window_data=action_window,
            )

            # Envelope Connection
            env_res = self.envelope_connector.evaluate_scenario_on_envelope(
                baseline_rain_mm=storm_rain_mm,
                baseline_temp_c=pre_storm_water_temp_c,
                pre_storm_do_mg_L=pre_storm_do_mg_L,
                pre_storm_discharge_cfs=pre_storm_discharge_cfs,
                intervention_type=itype,
                intervention_config=cfg,
                threshold_mg_L=thr,
            )

            scenarios_results[itype] = {
                "name": cfg.__class__.__name__,
                "simulation": {
                    "minimum_do_mg_L": mod_min_do,
                    "dissolved_oxygen_gain_mg_L": do_gain,
                    "time_to_nadir_hours": sim_res["time_to_nadir_hours"],
                    "hourly_do_trajectory": sim_res["hourly_do_trajectory_mg_L"],
                },
                "feasibility": feas_res,
                "envelope_mapping": env_res,
                "citations": InterventionParameters.get_citations_for(itype),
            }

        return {
            "status": "SUCCESS",
            "is_supported": True,
            "scenario_label": scenario_label,
            "inputs": {
                "pre_storm_water_temp_c": pre_storm_water_temp_c,
                "pre_storm_do_mg_L": pre_storm_do_mg_L,
                "pre_storm_discharge_cfs": pre_storm_discharge_cfs,
                "storm_rain_mm": storm_rain_mm,
                "storm_duration_hours": storm_duration_hours,
                "threshold_mg_L": thr,
                "operational_risk_limit": self.risk_limit,
            },
            "baseline": {
                "estimated_risk_probability": round(p_breach_72h, 4),
                "in_elevated_risk_zone": bool(p_breach_72h >= self.risk_limit),
                "simulated_minimum_do_mg_L": base_min_do,
                "simulated_nadir_time_hours": base_sim["time_to_nadir_hours"],
                "hourly_do_trajectory": base_sim["hourly_do_trajectory_mg_L"],
            },
            "action_window": action_window,
            "rehearsal_scenarios": scenarios_results,
            "scientific_disclaimer": SCIENTIFIC_SAFEGUARDS["causal_disclaimer"],
        }
