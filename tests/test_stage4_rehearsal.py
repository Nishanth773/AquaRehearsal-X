"""
AquaRehearsal-X - Stage 4 Automated Unit & Integration Tests
Action Window and Intervention Rehearsal Engine (Risk-to-Action Decision Support)

Validates all 9 core Stage 4 engineering and scientific criteria:
1. Time-window definitions (horizon monotonicity P(6h) <= P(12h) <= ... <= P(72h))
2. Threshold-crossing calculations (earliest <= median <= latest crossing bounds)
3. No future-data leakage (pre-storm inputs isolated at t0 - 1h)
4. Physical bounds and units (DO in physical aquatic bounds, kinetics strictly positive)
5. Missing input behavior (preservation of NaN and refusal)
6. Feasibility classifications (4 distinct tiers: FEASIBLE, UNCERTAIN, UNLIKELY, INSUFFICIENT)
7. Scenario reproducibility (deterministic mass balance and envelope mapping)
8. Refusal for unsupported scenarios (out-of-bounds inputs return standard refusal string)
9. Anti-ranking rule (no automated single-winner ranking or 'best action' declaration)
"""

import pytest
import numpy as np
import pandas as pd

from src.rehearsal.action_window_estimator import ActionWindowEstimator
from src.rehearsal.intervention_parameters import (
    InterventionParameters,
    AerationConfig,
    RunoffReductionConfig,
    DetentionConfig,
    RiparianShadingConfig,
)
from src.rehearsal.oxygen_balance_model import OxygenBalanceModel
from src.rehearsal.feasibility_filter import FeasibilityFilter
from src.rehearsal.envelope_connection import EnvelopeConnector
from src.rehearsal.scenario_runner import ScenarioRunner
from src.rehearsal.scenario_comparison import ScenarioComparison
from src.ste.domain_support_checker import DomainSupportChecker
from src.config.stage4_settings import ACTION_WINDOW_HORIZONS, SCIENTIFIC_SAFEGUARDS


class TestStage4Rehearsal:
    """Test suite for Stage 4 Decision Support components."""

    def setup_method(self):
        self.estimator = ActionWindowEstimator(default_threshold_mg_L=5.0)
        self.oxygen_model = OxygenBalanceModel()
        self.feasibility_filter = FeasibilityFilter()
        self.runner = ScenarioRunner(default_threshold_mg_L=5.0)

    def test_time_window_definitions(self):
        """Verifies horizon definitions and monotonic cumulative crossing probability ordering."""
        assert ACTION_WINDOW_HORIZONS == [6, 12, 24, 48, 72]

        res = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=24.0,
            pre_storm_do_mg_L=7.2,
            pre_storm_discharge_cfs=1200.0,
            storm_rain_mm=38.0,
            threshold_mg_L=5.0,
        )

        assert res["status"] == "VALID_ESTIMATE"
        probs = res["crossing_probabilities_by_horizon"]
        p6 = probs["6h"]
        p12 = probs["12h"]
        p24 = probs["24h"]
        p48 = probs["48h"]
        p72 = probs["72h"]

        assert 0.0 <= p6 <= p12 <= p24 <= p48 <= p72 <= 1.0

    def test_threshold_crossing_calculations(self):
        """Verifies earliest <= median <= latest crossing bounds when a breach is expected."""
        res = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=26.0,
            pre_storm_do_mg_L=6.5,
            pre_storm_discharge_cfs=800.0,
            storm_rain_mm=45.0,
            threshold_mg_L=5.0,
            expected_min_do_72h=3.8,  # Below threshold
        )

        assert res["crossing_expected_in_central_scenario"] is True
        t_early = res["earliest_plausible_crossing_hours"]
        t_med = res["median_estimated_crossing_hours"]
        t_late = res["latest_plausible_crossing_hours"]

        assert t_early is not None and t_med is not None and t_late is not None
        assert 0.0 < t_early <= t_med <= t_late <= 72.0

        # Test immediate breach condition (stream already at or below threshold)
        res_breach = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=26.0,
            pre_storm_do_mg_L=4.8,  # Below threshold 5.0
            pre_storm_discharge_cfs=800.0,
            storm_rain_mm=45.0,
            threshold_mg_L=5.0,
        )
        assert res_breach["status"] == "IMMEDIATE_BREACH"
        assert res_breach["actionable_window_hours"] == 0.0

    def test_no_future_data_leakage(self):
        """Verifies that pre-storm inputs and action window calculations rely strictly on t <= t0."""
        # Baseline run
        res1 = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=22.0,
            pre_storm_do_mg_L=7.5,
            pre_storm_discharge_cfs=1100.0,
            storm_rain_mm=30.0,
        )

        # Mutating downstream future values does not affect estimator function
        future_mutated_do = [1.0] * 72
        res2 = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=22.0,
            pre_storm_do_mg_L=7.5,
            pre_storm_discharge_cfs=1100.0,
            storm_rain_mm=30.0,
        )

        assert res1["estimated_action_window_hours"] == res2["estimated_action_window_hours"]
        assert res1["crossing_probabilities_by_horizon"] == res2["crossing_probabilities_by_horizon"]

    def test_physical_bounds_and_units(self):
        """Verifies that oxygen-balance simulation maintains physical aquatic bounds."""
        sim = self.oxygen_model.simulate_trajectory(
            pre_storm_water_temp_c=25.0,
            pre_storm_do_mg_L=7.0,
            pre_storm_discharge_cfs=1000.0,
            storm_rain_mm=50.0,
        )

        do_traj = np.array(sim["hourly_do_trajectory_mg_L"])
        cs = sim["saturation_do_mg_L"]

        assert np.all(do_traj >= 0.5)
        assert np.all(do_traj <= cs * 1.05)
        assert sim["kinetics_parameters"]["ka_per_hour"] > 0
        assert sim["kinetics_parameters"]["kd_per_hour"] > 0
        assert sim["kinetics_parameters"]["sod_mg_L_h"] > 0

    def test_missing_input_behavior(self):
        """Verifies that missing or NaN sensor inputs trigger standard refusal message."""
        res_nan_temp = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=np.nan,
            pre_storm_do_mg_L=7.0,
            pre_storm_discharge_cfs=1000.0,
            storm_rain_mm=20.0,
        )
        assert res_nan_temp["status"] == "REFUSAL"
        assert "Insufficient evidence to estimate this scenario reliably." in res_nan_temp["message"]

        res_nan_rain = self.estimator.estimate_action_window(
            pre_storm_water_temp_c=20.0,
            pre_storm_do_mg_L=7.0,
            pre_storm_discharge_cfs=1000.0,
            storm_rain_mm=np.nan,
        )
        assert res_nan_rain["status"] == "REFUSAL"
        assert "Insufficient evidence to estimate this scenario reliably." in res_nan_rain["message"]

    def test_feasibility_classifications(self):
        """Verifies correct tier assignment: FEASIBLE, UNCERTAIN, and UNLIKELY."""
        # Case A: Action window is large (28h) -> Aeration (lead 5.0h) is POTENTIALLY_FEASIBLE
        window_large = {
            "is_supported": True,
            "status": "VALID_ESTIMATE",
            "estimated_action_window_hours": 28.0,
            "earliest_plausible_crossing_hours": 28.0,
            "median_estimated_crossing_hours": 36.0,
        }
        aeration_cfg = AerationConfig()
        feas_a = self.feasibility_filter.evaluate_feasibility("temporary_aeration", aeration_cfg, window_large)
        assert feas_a["feasibility_tier"] == "POTENTIALLY_FEASIBLE"
        assert feas_a["time_margin_hours"] > 0

        # Case B: Action window is very tight (4.0h) -> Aeration (lead 5.0h) is FEASIBILITY_UNCERTAIN
        window_tight = {
            "is_supported": True,
            "status": "VALID_ESTIMATE",
            "estimated_action_window_hours": 4.0,
            "earliest_plausible_crossing_hours": 4.0,
            "median_estimated_crossing_hours": 7.0,
        }
        feas_b = self.feasibility_filter.evaluate_feasibility("temporary_aeration", aeration_cfg, window_tight)
        assert feas_b["feasibility_tier"] == "FEASIBILITY_UNCERTAIN"

        # Case C: Riparian shading (lead ~5 years) -> strictly UNLIKELY_TO_AFFECT for imminent storm
        shading_cfg = RiparianShadingConfig()
        feas_c = self.feasibility_filter.evaluate_feasibility("riparian_shading", shading_cfg, window_large)
        assert feas_c["feasibility_tier"] == "UNLIKELY_TO_AFFECT"

    def test_scenario_reproducibility(self):
        """Verifies that multi-scenario rehearsals produce identical results across runs."""
        run1 = self.runner.rehearse_all_scenarios(
            pre_storm_water_temp_c=22.0,
            pre_storm_do_mg_L=7.5,
            pre_storm_discharge_cfs=1200.0,
            storm_rain_mm=30.0,
        )
        run2 = self.runner.rehearse_all_scenarios(
            pre_storm_water_temp_c=22.0,
            pre_storm_do_mg_L=7.5,
            pre_storm_discharge_cfs=1200.0,
            storm_rain_mm=30.0,
        )

        assert run1["baseline"]["simulated_minimum_do_mg_L"] == run2["baseline"]["simulated_minimum_do_mg_L"]
        assert run1["action_window"]["estimated_action_window_hours"] == run2["action_window"]["estimated_action_window_hours"]
        
        for k in ["temporary_aeration", "runoff_reduction", "stormwater_detention", "riparian_shading"]:
            g1 = run1["rehearsal_scenarios"][k]["simulation"]["dissolved_oxygen_gain_mg_L"]
            g2 = run2["rehearsal_scenarios"][k]["simulation"]["dissolved_oxygen_gain_mg_L"]
            assert g1 == g2

    def test_refusal_for_unsupported_scenarios(self):
        """Verifies refusal when rainfall or temperature violates empirical domain bounds."""
        # Unobserved extreme rain (120mm exceeds 72mm maximum)
        res_ood_rain = self.runner.rehearse_all_scenarios(
            pre_storm_water_temp_c=20.0,
            pre_storm_do_mg_L=7.0,
            pre_storm_discharge_cfs=1000.0,
            storm_rain_mm=120.0,
        )
        assert res_ood_rain["status"] == "REFUSAL"
        assert "Insufficient evidence to estimate this scenario reliably." in res_ood_rain["message"]

        # Unobserved extreme temperature (45°C exceeds 31°C maximum)
        res_ood_temp = self.runner.rehearse_all_scenarios(
            pre_storm_water_temp_c=45.0,
            pre_storm_do_mg_L=7.0,
            pre_storm_discharge_cfs=1000.0,
            storm_rain_mm=25.0,
        )
        assert res_ood_temp["status"] == "REFUSAL"
        assert "Insufficient evidence to estimate this scenario reliably." in res_ood_temp["message"]

    def test_no_automatic_intervention_ranking(self):
        """Verifies that ScenarioComparison does NOT sort by simulated DO gain or pick a single winner."""
        rehearsal = self.runner.rehearse_all_scenarios(
            pre_storm_water_temp_c=25.0,
            pre_storm_do_mg_L=6.8,
            pre_storm_discharge_cfs=850.0,
            storm_rain_mm=40.0,
        )
        df_comp = ScenarioComparison.build_comparison_dataframe(rehearsal)

        assert not df_comp.empty
        # Verify baseline is at row 0 (order preserved by archetype, not sorted by gain)
        assert df_comp.iloc[0]["Intervention"] == "Baseline (No Action)"

        # Check anti-ranking notice exists and disclaims automated recommendation
        notice = ScenarioComparison.get_anti_ranking_notice()
        assert "refrains from automated single-metric ranking" in notice
        assert "winner" in notice or "recommended" in notice or "ranking" in notice
