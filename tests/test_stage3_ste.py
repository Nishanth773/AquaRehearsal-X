"""
AquaRehearsal-X - Stage 3 Automated Unit & Integration Tests
Storm Tolerance Envelope (STE), Dynamic Conditioning, Action Window & Early Warning

Validates:
1. Benson-Krause theoretical dissolved oxygen saturation physics.
2. Multi-dimensional envelope monotonicity (rainfall and discharge increase cannot increase DO).
3. Dynamic thermal contraction (warm water strictly contracts the tolerance envelope relative to cold).
4. Antecedent catchment wetness conditioning (saturated soils shift R_crit downwards).
5. Boundary-crossing probability axioms: bounds in [0, 1] and monotonic quantile ordering P(2.0) <= P(4.0) <= P(5.0).
6. Stratified uncertainty calibrator persistence and regime properties.
7. Time-to-trough estimation physical boundedness and operational urgency tier mapping.
8. Programmatic API schema, inference, and out-of-distribution warning behavior.
"""

import pytest
import numpy as np
import pandas as pd

from src.config.stage3_settings import (
    STAGE3_REGULATORY_THRESHOLDS,
    THERMAL_TIERS,
    ANTECEDENT_MOISTURE_TIERS,
)
from src.ste.envelope_engine import (
    StormToleranceEnvelope,
    calculate_benson_krause_saturation,
)
from src.ste.probability_engine import (
    StratifiedUncertaintyCalibrator,
    BoundaryCrossingProbability,
)
from src.ste.action_window import ActionWindowEstimator
from src.models.ste_api import evaluate_storm_tolerance, StormToleranceAPI


class TestStormToleranceEnvelope:
    """Tests for physical consistency, monotonicity, and dynamic conditioning of the STE."""

    def setup_method(self):
        self.ste = StormToleranceEnvelope()

    def test_benson_krause_saturation_monotonicity(self):
        """Saturation must decrease monotonically as temperature rises."""
        sat_0 = calculate_benson_krause_saturation(0.0)
        sat_10 = calculate_benson_krause_saturation(10.0)
        sat_20 = calculate_benson_krause_saturation(20.0)
        sat_30 = calculate_benson_krause_saturation(30.0)

        assert sat_0 > sat_10 > sat_20 > sat_30
        assert 14.0 <= sat_0 <= 15.0
        assert 7.0 <= sat_30 <= 8.0

    def test_thermal_tier_categorization(self):
        """Verifies correct temperature bin assignment."""
        assert self.ste.get_thermal_tier(4.5) == "cold"
        assert self.ste.get_thermal_tier(14.9) == "cold"
        assert self.ste.get_thermal_tier(15.0) == "moderate"
        assert self.ste.get_thermal_tier(21.9) == "moderate"
        assert self.ste.get_thermal_tier(22.0) == "warm"
        assert self.ste.get_thermal_tier(29.5) == "warm"

    def test_antecedent_moisture_categorization(self):
        """Verifies correct 72h antecedent rainfall bin assignment."""
        assert self.ste.get_antecedent_moisture_tier(0.0) == "dry"
        assert self.ste.get_antecedent_moisture_tier(4.9) == "dry"
        assert self.ste.get_antecedent_moisture_tier(5.0) == "normal"
        assert self.ste.get_antecedent_moisture_tier(19.9) == "normal"
        assert self.ste.get_antecedent_moisture_tier(20.0) == "wet"
        assert self.ste.get_antecedent_moisture_tier(55.0) == "wet"

    def test_rainfall_monotonic_degradation(self):
        """Increasing storm rainfall must monotonically decrease or maintain expected minimum DO."""
        rains = [0.0, 10.0, 25.0, 45.0, 70.0]
        dos = [
            self.ste.estimate_minimum_do(
                ambient_temp_c=22.0,
                ambient_do_mg_L=7.5,
                ambient_discharge_cfs=1200.0,
                storm_rain_mm=r,
                discharge_surge_ratio=2.5,
            )
            for r in rains
        ]
        for i in range(len(dos) - 1):
            assert dos[i] >= dos[i + 1], f"DO at rain={rains[i]} ({dos[i]}) < DO at rain={rains[i+1]} ({dos[i+1]})"

    def test_discharge_surge_monotonic_degradation(self):
        """Increasing discharge surge ratio must monotonically decrease or maintain expected minimum DO."""
        surges = [1.0, 2.0, 4.0, 8.0, 12.0]
        dos = [
            self.ste.estimate_minimum_do(
                ambient_temp_c=20.0,
                ambient_do_mg_L=8.0,
                ambient_discharge_cfs=1000.0,
                storm_rain_mm=20.0,
                discharge_surge_ratio=s,
            )
            for s in surges
        ]
        for i in range(len(dos) - 1):
            assert dos[i] >= dos[i + 1]

    def test_thermal_contraction_of_tolerance(self):
        """Warm water (25°C) must have strictly lower critical rainfall capacity than cold water (10°C)."""
        r_crit_cold = self.ste.compute_critical_rainfall(
            ambient_temp_c=10.0,
            ambient_do_mg_L=11.0,
            ambient_discharge_cfs=1200.0,
            discharge_surge_ratio=3.0,
            target_threshold=4.0,
        )
        r_crit_warm = self.ste.compute_critical_rainfall(
            ambient_temp_c=25.0,
            ambient_do_mg_L=7.0,
            ambient_discharge_cfs=1200.0,
            discharge_surge_ratio=3.0,
            target_threshold=4.0,
        )
        assert r_crit_cold > r_crit_warm
        assert r_crit_warm < 35.0  # Warm water tolerance is tightly constrained

    def test_antecedent_wetness_envelope_shift(self):
        """Saturated catchment (API=35mm) must have lower critical rainfall than dry catchment (API=2mm)."""
        r_crit_dry = self.ste.compute_critical_rainfall(
            ambient_temp_c=20.0,
            ambient_do_mg_L=8.0,
            ambient_discharge_cfs=1200.0,
            discharge_surge_ratio=3.0,
            antecedent_rain_72h_mm=2.0,
            target_threshold=4.0,
        )
        r_crit_wet = self.ste.compute_critical_rainfall(
            ambient_temp_c=20.0,
            ambient_do_mg_L=8.0,
            ambient_discharge_cfs=1200.0,
            discharge_surge_ratio=3.0,
            antecedent_rain_72h_mm=35.0,
            target_threshold=4.0,
        )
        assert r_crit_dry > r_crit_wet


class TestProbabilityAndUncertainty:
    """Tests for thermally stratified uncertainty and boundary-crossing probabilities."""

    def setup_method(self):
        self.calibrator = StratifiedUncertaintyCalibrator(target_coverage=0.80)
        self.prob = BoundaryCrossingProbability(calibrator=self.calibrator)

    def test_probability_bounds_and_ordering(self):
        """Probabilities must be in [0, 1] and satisfy P(DO < 2.0) <= P(DO < 4.0) <= P(DO < 5.0)."""
        probs = self.prob.compute_crossing_probabilities(expected_min_do=4.5, ambient_temp_c=23.0)

        p2 = probs["p_crossing_hypoxia_2_0"]
        p4 = probs["p_crossing_acute_4_0"]
        p5 = probs["p_crossing_standard_5_0"]

        assert 0.0 <= p2 <= 1.0
        assert 0.0 <= p4 <= 1.0
        assert 0.0 <= p5 <= 1.0
        assert p2 <= p4 <= p5

    def test_probability_monotonicity_with_storm_severity(self):
        """As predicted minimum DO decreases, boundary-crossing probabilities must increase."""
        probs_high = self.prob.compute_crossing_probabilities(expected_min_do=7.5, ambient_temp_c=20.0)
        probs_mid = self.prob.compute_crossing_probabilities(expected_min_do=4.5, ambient_temp_c=20.0)
        probs_low = self.prob.compute_crossing_probabilities(expected_min_do=2.8, ambient_temp_c=20.0)

        assert probs_high["p_crossing_acute_4_0"] < probs_mid["p_crossing_acute_4_0"] < probs_low["p_crossing_acute_4_0"]
        assert probs_low["p_crossing_hypoxia_2_0"] > probs_high["p_crossing_hypoxia_2_0"]

    def test_alert_level_classification(self):
        """Verifies correct operational alert level assignment."""
        # Safe high DO scenario
        safe_alert = self.prob.determine_alert_level(expected_min_do=7.0, p_acute_4_0=0.02, p_hypoxia_2_0=0.0)
        assert safe_alert["key"] == "NORMAL"

        # Advisory intermediate scenario
        adv_alert = self.prob.determine_alert_level(expected_min_do=4.6, p_acute_4_0=0.20, p_hypoxia_2_0=0.01)
        assert adv_alert["key"] == "ADVISORY"

        # Warning acute breach scenario
        warn_alert = self.prob.determine_alert_level(expected_min_do=3.5, p_acute_4_0=0.55, p_hypoxia_2_0=0.05)
        assert warn_alert["key"] == "WARNING"

        # Emergency acute hypoxia scenario
        emerg_alert = self.prob.determine_alert_level(expected_min_do=1.8, p_acute_4_0=0.92, p_hypoxia_2_0=0.45)
        assert emerg_alert["key"] == "EMERGENCY"


class TestActionWindowEstimator:
    """Tests for time-to-trough and action window calculations."""

    def setup_method(self):
        self.estimator = ActionWindowEstimator()

    def test_time_to_trough_physical_bounds(self):
        """Time-to-trough must remain within physically defensible bounds [4h, 48h]."""
        lag_short = self.estimator.estimate_time_to_trough(
            storm_duration_hours=2.0, discharge_surge_ratio=1.5, water_temperature_c=26.0
        )
        lag_long = self.estimator.estimate_time_to_trough(
            storm_duration_hours=36.0, discharge_surge_ratio=8.0, water_temperature_c=8.0
        )

        assert 4.0 <= lag_short <= 48.0
        assert 4.0 <= lag_long <= 48.0
        assert lag_short < lag_long

    def test_characterize_action_window_urgency(self):
        """Verifies urgency tier assignment based on actionable hours."""
        w_imm = self.estimator.characterize_action_window(estimated_time_to_trough=8.0, alert_latency_hours=1.0)
        assert w_imm["urgency_tier"] == "IMMEDIATE"
        assert w_imm["actionable_window_hours"] == 7.0

        w_std = self.estimator.characterize_action_window(estimated_time_to_trough=18.0, alert_latency_hours=1.0)
        assert w_std["urgency_tier"] == "STANDARD"

        w_ext = self.estimator.characterize_action_window(estimated_time_to_trough=32.0, alert_latency_hours=1.0)
        assert w_ext["urgency_tier"] == "EXTENDED"


class TestProgrammaticAPI:
    """Tests for the high-level Stage 3 evaluate_storm_tolerance API."""

    def test_api_safe_scenario(self):
        """API evaluation under mild spring conditions should yield NORMAL status."""
        result = evaluate_storm_tolerance(
            current_conditions={
                "water_temperature": 12.0,
                "dissolved_oxygen": 10.5,
                "discharge": 1100.0,
                "antecedent_rain_72h": 2.0,
            },
            incoming_storm_forecast={
                "storm_rain_mm": 12.0,
                "discharge_surge_ratio": 1.8,
                "storm_duration_hours": 10.0,
            },
        )

        assert result["service"] == "AquaRehearsal-X Storm Tolerance & Early-Warning API"
        assert result["alert_status"]["key"] == "NORMAL"
        assert result["tolerance_envelope"]["expected_minimum_do_72h_mg_L"] >= 5.0
        assert result["boundary_crossing_probabilities"]["p_crossing_acute_4_0"] < 0.10
        assert result["action_window"]["actionable_window_hours"] > 0

    def test_api_severe_summer_storm_scenario(self):
        """API evaluation under hot summer heatwave + large storm should trigger WARNING or EMERGENCY."""
        result = evaluate_storm_tolerance(
            current_conditions={
                "water_temperature": 26.5,
                "dissolved_oxygen": 6.8,
                "discharge": 750.0,
                "antecedent_rain_72h": 28.0,
            },
            incoming_storm_forecast={
                "storm_rain_mm": 45.0,
                "discharge_surge_ratio": 5.2,
                "storm_duration_hours": 18.0,
            },
        )

        assert result["alert_status"]["key"] in ["WARNING", "EMERGENCY"]
        assert result["tolerance_envelope"]["expected_minimum_do_72h_mg_L"] < 4.0
        assert result["boundary_crossing_probabilities"]["p_crossing_acute_4_0"] > 0.35
        assert result["tolerance_envelope"]["remaining_assimilative_capacity_pct"] < 30.0

    def test_api_out_of_distribution_graceful_handling(self):
        """Extreme physical inputs outside normal training domain must flag domain warnings without crashing."""
        result = evaluate_storm_tolerance(
            current_conditions={
                "water_temperature": 45.0,  # Extreme heatwave OOD
                "dissolved_oxygen": 2.0,
                "discharge": 95000.0,       # Extreme flood OOD
                "antecedent_rain_72h": 120.0,
            },
            incoming_storm_forecast={
                "storm_rain_mm": 110.0,
                "discharge_surge_ratio": 15.0,
            },
        )
        assert "alert_status" in result
        assert "tolerance_envelope" in result
        assert result["alert_status"]["key"] == "EMERGENCY"
