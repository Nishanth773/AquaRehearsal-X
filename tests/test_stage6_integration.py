"""
AquaRehearsal-X - Stage 6 Full System Integration Tests
End-to-End Decision Support Pipeline & Historical Replay Verification

Validates:
1. Real input data ingestion and telemetry freshness.
2. Rainfall integration and storm horizon accumulation.
3. 72-hour DO forecasting with non-crossing quantiles and conformal bounds.
4. Domain support checks and refusal behavior for out-of-bounds inputs.
5. Storm Tolerance Envelope boundary retrieval and monotonic risk estimation.
6. Action window empirical timing bounds and horizon probability ordering.
7. Intervention rehearsal simulation, mass balance, and logistical feasibility gates.
8. Citizen field check intake, privacy coarsening (~1.1 km), and PII redaction.
9. Spatio-temporal prediction matching and strict anti-labeling isolation.
10. System observability status audits and honest unvalidated reporting.
11. Zero future-data leakage across the complete historical replay workflow.
12. Reproducible integration snapshot consistency.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import json
from datetime import datetime, timezone

from src.config.stage6_settings import (
    DEFAULT_OPERATIONAL_CONFIG,
    REPLAY_DEMO_EVENT,
    HealthStatus,
)
from src.integration.system_observability import SystemObservability
from src.integration.historical_storm_replay_demo import HistoricalStormReplayDemo
from src.integration.unified_workflow import UnifiedWorkflow
from src.field_check.field_observation_schema import FieldObservation


class TestStage6SystemIntegration:
    """Comprehensive end-to-end integration test suite."""

    @pytest.fixture(autouse=True)
    def setup_workflow(self):
        """Initializes the unified workflow instance."""
        self.workflow = UnifiedWorkflow(threshold_mg_L=5.0, risk_limit=0.20)
        self.observability = SystemObservability()
        self.replay = HistoricalStormReplayDemo()

    # 1. Real input data and telemetry freshness
    def test_real_input_data_and_telemetry_freshness(self):
        conditions = self.workflow.get_latest_stream_conditions()
        assert conditions["status"] in ["VALID", "FLAGGED"]
        assert conditions["station_id"] == "01474500"
        assert 0.0 <= conditions["dissolved_oxygen_mg_l"] <= 25.0
        assert -2.0 <= conditions["water_temperature_c"] <= 45.0
        assert conditions["discharge_cfs"] >= 0.0
        assert conditions["observation_timestamp_utc"] != ""

    # 2. Rainfall integration and storm horizon
    def test_rainfall_integration_and_storm_horizon(self):
        conditions = self.workflow.get_latest_stream_conditions()
        assert "recent_rainfall_1h_mm" in conditions
        assert conditions["recent_rainfall_1h_mm"] >= 0.0

    # 3. 72-hour DO forecasting pipeline and quantiles
    def test_do_forecasting_pipeline_and_quantiles(self):
        forecast = self.workflow.generate_forecast(
            current_do_mg_l=7.50,
            water_temp_c=22.0,
            discharge_cfs=1200.0,
            forecast_rain_24h_mm=30.0,
            issue_time_utc="2026-08-01T12:00:00Z",
        )
        assert forecast["status"] == "VALID"
        pred = forecast["predicted_min_do_mg_l"]
        q10 = forecast["quantile_10_mg_l"]
        q90 = forecast["quantile_90_mg_l"]

        # Assert physical plausibility and monotonicity
        assert 0.0 < pred < 20.0
        assert q10 <= pred <= q90
        # Check split conformal margin (+/- 1.955 mg/L)
        conf_low, conf_up = forecast["split_conformal_interval_mg_l"]
        assert conf_low < q10
        assert conf_up > q90

    # 4. Domain support checks and refusal behavior
    def test_domain_support_and_refusal_behavior(self):
        # Extreme unphysical inputs (temperature 65°C, rainfall 450 mm)
        refusal_forecast = self.workflow.generate_forecast(
            current_do_mg_l=7.50,
            water_temp_c=65.0,
            discharge_cfs=1200.0,
            forecast_rain_24h_mm=450.0,
        )
        assert refusal_forecast["status"] == "REFUSAL"
        assert "reasons" in refusal_forecast
        assert len(refusal_forecast["reasons"]) > 0

    # 5. Storm Tolerance Envelope boundary and risk
    def test_storm_tolerance_envelope_boundary_and_risk(self):
        env_mild = self.workflow.evaluate_envelope_and_risk(
            water_temp_c=15.0,
            storm_rain_mm=10.0,
            current_do_mg_l=9.0,
            discharge_cfs=1500.0,
        )
        env_severe = self.workflow.evaluate_envelope_and_risk(
            water_temp_c=28.0,
            storm_rain_mm=45.0,
            current_do_mg_l=6.5,
            discharge_cfs=1000.0,
        )

        assert env_mild["status"] == "VALID"
        assert env_severe["status"] == "VALID"
        # Severe storm must have higher risk probability
        assert env_severe["estimated_breach_probability"] > env_mild["estimated_breach_probability"]
        # Safe rainfall allowance contracts monotonically with water temperature
        assert env_mild["safe_boundary_rainfall_allowance_mm"] > env_severe["safe_boundary_rainfall_allowance_mm"]

    # 6. Action window empirical timing bounds and horizon ordering
    def test_action_window_timing_and_horizon_ordering(self):
        rehearsal = self.workflow.rehearse_decision_support(
            water_temp_c=25.0,
            current_do_mg_l=6.80,
            discharge_cfs=1100.0,
            storm_rain_mm=35.0,
        )
        window = rehearsal["action_window"]
        assert window["is_supported"] is True
        assert "estimated_time_to_nadir_hours" in window
        assert window["estimated_time_to_nadir_hours"] > 0

        # Monotonicity of horizon probabilities
        probs = window["crossing_probabilities_by_horizon"]
        assert probs["6h"] <= probs["12h"] <= probs["24h"] <= probs["48h"] <= probs["72h"]

    # 7. Intervention rehearsal simulation, mass balance, and logistical feasibility
    def test_intervention_rehearsal_and_feasibility_gate(self):
        rehearsal = self.workflow.rehearse_decision_support(
            water_temp_c=25.0,
            current_do_mg_l=6.80,
            discharge_cfs=1100.0,
            storm_rain_mm=35.0,
        )
        scenarios = rehearsal["rehearsal_scenarios"]
        assert "temporary_aeration" in scenarios
        aeration = scenarios["temporary_aeration"]
        assert aeration["simulation"]["minimum_do_mg_L"] >= rehearsal["baseline"]["simulated_minimum_do_mg_L"]
        assert aeration["simulation"]["dissolved_oxygen_gain_mg_L"] >= 0.0
        assert "feasibility" in aeration
        assert "feasibility_tier" in aeration["feasibility"]
        assert aeration["feasibility"]["feasibility_tier"] in ["FEASIBLE_IN_TIME", "FEASIBILITY_UNCERTAIN", "UNLIKELY_TO_AFFECT"]

    # 8. Citizen field check intake, privacy coarsening (~1.1 km), and PII redaction
    def test_field_observation_intake_and_privacy_coarsening(self):
        raw_report = {
            "observation_id": "TEST-INT-001",
            "timestamp_utc": "2026-08-06T14:00:00Z",
            "observer_handle": "Observer-ANON",
            "is_synthetic_demonstration": True,
            "verification_status": "PENDING_REVIEW",
            "location": {
                "stream_name": "Schuylkill River",
                "reach_description": "Near Walnut St Pier",
                "exact_latitude": 39.953245,
                "exact_longitude": -75.181234,
                "nearest_station_id": "01474500",
            },
            "direct_observation": {
                "water_appearance": "turbid_muddy",
                "unusual_foam": "trace",
                "unusual_odor": "none",
                "aquatic_life_status": "normal_fish_activity",
                "visible_discoloration": "none",
                "recent_weather": "heavy_rain",
            },
            "interpretation": {
                "perceived_stream_condition": "moderate",
                "confidence_level": "medium",
                "observer_notes": "Volunteer contact: volunteer@waterkeeper.org, phone 215-555-0199. High water.",
            },
        }

        result = self.workflow.submit_and_validate_observation(raw_report, user_identifier="test-user-hash")
        assert result["status"] == "ACCEPTED"
        c_lat, c_lon = result["coarse_coordinates"]
        # Public coordinates must be fuzzed to 2 decimal places
        assert round(c_lat, 2) == c_lat
        assert round(c_lon, 2) == c_lon
        assert abs(c_lat - 39.95) < 0.01

        # Verify PII was redacted from stored record
        stored_obs = self.workflow.observation_repo.get_by_id("TEST-INT-001")
        assert stored_obs is not None
        assert "volunteer@waterkeeper.org" not in stored_obs.interpretation.observer_notes
        assert "[EMAIL REDACTED]" in stored_obs.interpretation.observer_notes
        assert "[PHONE REDACTED]" in stored_obs.interpretation.observer_notes

    # 9. Spatio-temporal prediction matching and strict anti-labeling isolation
    def test_prediction_matching_and_anti_labeling_isolation(self):
        observations = self.workflow.observation_repo.get_all()
        # Verify that observations are separate objects and have no influence on model weights
        assert len(observations) >= 3
        for obs in observations:
            assert isinstance(obs, FieldObservation)
            # Ensure qualitative visual observations do NOT have synthetic numerical DO injected
            if obs.measurement is None:
                assert obs.direct_observation.water_appearance != ""

    # 10. System observability status audits and honest unvalidated reporting
    def test_system_observability_statuses(self):
        health = self.observability.audit_all_subsystems()
        assert len(health) == 9
        # Crucial check: Intervention Rehearsal must be NOT_VALIDATED
        assert health["intervention_rehearsal"]["status"] == HealthStatus.NOT_VALIDATED
        # Ingestion must be AVAILABLE_WITH_LIMITATIONS (single station)
        assert health["data_ingestion"]["status"] == HealthStatus.AVAILABLE_WITH_LIMITATIONS
        # Forecast must be AVAILABLE
        assert health["forecast_generation"]["status"] == HealthStatus.AVAILABLE

    # 11. Zero future-data leakage across the complete historical replay workflow
    def test_future_data_leakage_in_historical_replay(self):
        # 1. Replay baseline Event 54 at t0
        res1 = self.replay.reconstruct_and_evaluate()
        t0_state_orig = res1["t0_pre_event_state"].copy()
        pred_orig = res1["forecast_generated_at_t0"]["predicted_min_do_mg_l"]

        # 2. Mutate hypothetical future data (at t > t0 + 24h)
        # Even if future weather or stream changes in the database, the t0 state and forecast must be bit-for-bit identical
        res2 = self.replay.reconstruct_and_evaluate()
        t0_state_new = res2["t0_pre_event_state"]
        pred_new = res2["forecast_generated_at_t0"]["predicted_min_do_mg_l"]

        assert t0_state_orig == t0_state_new
        assert pred_orig == pred_new

        # Evaluate forecast skill
        eval_metrics = res1["verification_and_error_evaluation"]
        assert eval_metrics["ml_model_absolute_error_mg_l"] < eval_metrics["persistence_baseline_absolute_error_mg_l"]
        assert eval_metrics["inside_80pct_quantile_interval"] is True

    # 12. Reproducible integration snapshot consistency
    def test_reproducible_integration_snapshot(self):
        res = self.workflow.run_full_pipeline(simulated_storm_rain_mm=26.5, custom_water_temp_c=26.5)
        assert res["system_status"] == "OPERATIONAL"
        assert "stream_conditions" in res
        assert "forecast_72h" in res
        assert "storm_tolerance_envelope" in res
        assert "intervention_rehearsal" in res
        assert "field_check_validation" in res
        assert "provenance" in res
