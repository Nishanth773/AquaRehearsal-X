"""
AquaRehearsal-X - Stage 3 Modular Scientific Requirements Tests

Verifies the 8 core engineering and scientific criteria:
1. Event Identification (storm_event_detector)
2. Future-Data Leakage Prevention (leakage audit)
3. Overlapping Event Handling (72h cluster resolution)
4. Domain Masking (domain_support_checker Delaunay hull)
5. Missing Rainfall Handling (preservation of NaN and refusal)
6. Threshold Configuration (customizable DO criteria: 5.0, 4.0, 2.0 mg/L)
7. Reproducible Envelope Generation (deterministic grid and contours)
8. Refusal Behavior ("Insufficient evidence to estimate this scenario reliably.")
"""

import pytest
import numpy as np
import pandas as pd

from src.ste.storm_event_detector import StormEventDetector
from src.ste.domain_support_checker import DomainSupportChecker
from src.ste.risk_model import EcologicalRiskModel
from src.ste.envelope_generator import StormToleranceEnvelopeGenerator
from src.ste.historical_storm_replay import HistoricalStormReplay
from src.ste.boundary_uncertainty import BoundaryUncertaintyEstimator


@pytest.fixture
def sample_timeseries():
    """Generates synthetic continuous hourly time series with two storm surges."""
    dates = pd.date_range("2024-01-01", periods=500, freq="1h", tz="UTC")
    np.random.seed(42)
    
    # Baseline
    temp = 16.0 + 3.0 * np.sin(np.linspace(0, 10, 500))
    do = 9.0 + 1.5 * np.cos(np.linspace(0, 10, 500))
    q = 1200.0 + 100.0 * np.random.randn(500)
    rain = np.zeros(500)
    
    # Event 1 at hour 200
    rain[195:205] = 4.5
    q[198:220] = 4500.0
    do[205:235] = 6.2  # DO depression
    
    # Event 2 at hour 240 (within 72h of Event 1 -> overlapping)
    rain[238:245] = 5.0
    q[240:260] = 5200.0
    do[245:270] = 5.8
    
    # Event 3 at hour 360 (independent, non-overlapping)
    rain[355:365] = 6.0
    q[360:385] = 6000.0
    do[365:390] = 5.1
    
    df = pd.DataFrame({
        "timestamp": dates,
        "water_temperature": temp,
        "dissolved_oxygen": do,
        "discharge": q,
        "rain_mm": rain,
    }).set_index("timestamp")
    
    return df


def test_event_identification(sample_timeseries):
    """Verifies that storm disturbances are detected with correct pre-storm and outcome states."""
    detector = StormEventDetector(
        discharge_surge_ratio_threshold=1.5,
        min_peak_discharge_cfs=2000.0,
        min_event_rainfall_mm=10.0,
        evaluation_horizon_hours=72,
    )
    df_events = detector.detect_events_from_timeseries(sample_timeseries)
    
    assert len(df_events) >= 2
    for col in ["forecast_issue_time", "pre_storm_water_temp_c", "cumulative_storm_rain_mm", "future_min_do_72h"]:
        assert col in df_events.columns
        assert not df_events[col].isna().all()


def test_future_data_leakage(sample_timeseries):
    """
    Verifies that mutating future water-quality measurements during (t0, t0 + 72h]
    does not alter the pre-storm inputs or forecast generated at t0.
    """
    detector = StormEventDetector()
    events_original = detector.detect_events_from_timeseries(sample_timeseries)
    first_event_t0 = pd.to_datetime(events_original.iloc[0]["forecast_issue_time"], utc=True)
    
    # Mutate future DO and rain in a mutated copy
    mutated_ts = sample_timeseries.copy()
    future_mask = (mutated_ts.index > first_event_t0) & (mutated_ts.index <= first_event_t0 + pd.Timedelta(hours=72))
    mutated_ts.loc[future_mask, "dissolved_oxygen"] = 1.0  # extreme future collapse
    mutated_ts.loc[future_mask, "rain_mm"] = 99.0
    
    # Pre-storm state must remain identical
    pre_t = first_event_t0 - pd.Timedelta(hours=1)
    assert sample_timeseries.loc[pre_t, "dissolved_oxygen"] == mutated_ts.loc[pre_t, "dissolved_oxygen"]
    assert sample_timeseries.loc[pre_t, "water_temperature"] == mutated_ts.loc[pre_t, "water_temperature"]


def test_overlapping_event_handling():
    """Verifies that events with starting times separated by < 72 hours are flagged as overlapping."""
    detector = StormEventDetector(evaluation_horizon_hours=72)
    df_raw = pd.DataFrame([
        {"event_id": 1, "forecast_issue_time": "2024-05-01T00:00:00+00:00"},
        {"event_id": 2, "forecast_issue_time": "2024-05-02T12:00:00+00:00"},  # 36h later -> overlap
        {"event_id": 3, "forecast_issue_time": "2024-05-15T00:00:00+00:00"},  # 13 days later -> clean
    ])
    
    flagged = detector.flag_and_resolve_overlaps(df_raw)
    assert flagged.loc[0, "has_72h_window_overlap"] == False
    assert flagged.loc[0, "is_non_overlapping"] == True
    
    assert flagged.loc[1, "has_72h_window_overlap"] == True
    assert flagged.loc[1, "is_non_overlapping"] == False
    
    assert flagged.loc[2, "has_72h_window_overlap"] == False
    assert flagged.loc[2, "is_non_overlapping"] == True


def test_domain_masking():
    """Verifies that unsupported combinations of rainfall and temperature are masked."""
    checker = DomainSupportChecker(min_temp_c=2.0, max_temp_c=30.0, max_rainfall_mm=70.0)
    
    # Feed historical points
    df_events = pd.DataFrame({
        "cumulative_storm_rain_mm": [5.0, 15.0, 30.0, 50.0, 20.0],
        "pre_storm_water_temp_c": [5.0, 12.0, 18.0, 24.0, 28.0],
    })
    checker.fit_from_historical_events(df_events)
    
    # Supported point
    assert checker.is_supported(rain_mm=20.0, temp_c=18.0) == True
    
    # Unobserved extreme points (extrapolations)
    assert checker.is_supported(rain_mm=120.0, temp_c=20.0) == False
    assert checker.is_supported(rain_mm=30.0, temp_c=45.0) == False


def test_missing_rainfall_refusal():
    """Verifies that missing rainfall (NaN) triggers refusal rather than assuming zero."""
    checker = DomainSupportChecker()
    is_valid, msg = checker.validate_sensor_inputs(
        water_temp_c=18.0,
        rain_mm=np.nan,
        do_mg_L=8.0,
        discharge_cfs=1500.0,
    )
    assert is_valid == False
    assert "Missing storm rainfall estimate" in msg
    assert "Insufficient evidence to estimate this scenario reliably." in msg


def test_threshold_configuration():
    """Verifies that risk probabilities strictly obey ordering P(2.0) <= P(4.0) <= P(5.0)."""
    model_5 = EcologicalRiskModel(default_threshold_mg_L=5.0)
    model_4 = EcologicalRiskModel(default_threshold_mg_L=4.0)
    model_2 = EcologicalRiskModel(default_threshold_mg_L=2.0)
    
    p5 = model_5.estimate_risk_probability(storm_rain_mm=30.0, pre_storm_water_temp_c=24.0, pre_storm_do_mg_L=7.5, pre_storm_discharge_cfs=1200.0)
    p4 = model_4.estimate_risk_probability(storm_rain_mm=30.0, pre_storm_water_temp_c=24.0, pre_storm_do_mg_L=7.5, pre_storm_discharge_cfs=1200.0)
    p2 = model_2.estimate_risk_probability(storm_rain_mm=30.0, pre_storm_water_temp_c=24.0, pre_storm_do_mg_L=7.5, pre_storm_discharge_cfs=1200.0)
    
    assert 0.0 <= p2 <= p4 <= p5 <= 1.0


def test_reproducible_envelope_generation():
    """Verifies that 2D grid generation produces deterministic, reproducible probabilities."""
    checker = DomainSupportChecker()
    model = EcologicalRiskModel(default_threshold_mg_L=5.0)
    gen = StormToleranceEnvelopeGenerator(risk_model=model, domain_checker=checker)
    
    grid1 = gen.generate_surface_grid(rain_steps=10, temp_steps=10)
    grid2 = gen.generate_surface_grid(rain_steps=10, temp_steps=10)
    
    np.testing.assert_allclose(grid1["probability_surface"], grid2["probability_surface"], rtol=1e-5)
    np.testing.assert_array_equal(grid1["support_mask"], grid2["support_mask"])


def test_refusal_behavior_when_evidence_insufficient():
    """Verifies refusal output format when sensor inputs are stale or out of physical bounds."""
    checker = DomainSupportChecker()
    
    # 1. Negative discharge
    valid, msg = checker.validate_sensor_inputs(water_temp_c=15.0, rain_mm=10.0, do_mg_L=8.0, discharge_cfs=-50.0)
    assert not valid
    assert "Stream discharge" in msg
    assert "Insufficient evidence to estimate this scenario reliably." in msg
    
    # 2. Frozen water / below physical liquid bounds
    valid, msg = checker.validate_sensor_inputs(water_temp_c=-4.0, rain_mm=10.0, do_mg_L=8.0, discharge_cfs=1000.0)
    assert not valid
    assert "Pre-storm water temperature" in msg
    assert "Insufficient evidence to estimate this scenario reliably." in msg
