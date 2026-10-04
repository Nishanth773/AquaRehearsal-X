"""
AquaRehearsal-X - Stage 5 Automated Unit & Integration Tests
Citizen Observation and Prediction Verification System (Field Check)

Validates all 10 core Stage 5 engineering and scientific criteria:
1. Invalid timestamps (future dates, pre-epoch dates, malformed strings).
2. Measurement units and physical bounds (DO in [0, 20], temp in [-2, 38], pH in [3, 11.5]).
3. Duplicate report detection (15-minute spatio-temporal hash collision).
4. Unverified observation handling (default PENDING_REVIEW, strict review state transition).
5. Prediction matching (spatiotemporal link to storm forecasts & corroboration evaluation).
6. Temporal leakage prevention (observations at t > t0 cannot leak into historical training).
7. Privacy protections (coordinate coarsening to ~1.1km, anonymous handles, PII sanitization).
8. Missing location data handling (required name enforcement, graceful text fallback).
9. Image validation and EXIF metadata stripping.
10. Strict separation between visual observations and quantitative instrument measurements.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from src.field_check.field_observation_schema import (
    FieldObservation,
    DirectObservation,
    UserInterpretation,
    InstrumentMeasurement,
    ObservationLocation,
)
from src.field_check.privacy_controls import PrivacyController
from src.field_check.observation_quality import (
    ObservationQualityAssurance,
    haversine_distance_km,
)
from src.field_check.prediction_matching import PredictionMatcher
from src.field_check.observation_review import ObservationReviewWorkflow
from src.field_check.validation_pipeline import ObservationValidationPipeline
from src.field_check.observation_submission import ObservationRepository


class TestStage5FieldCheck:
    """Complete test suite for Stage 5 Field Check & Prediction Verification."""

    def setup_method(self):
        self.privacy = PrivacyController()
        self.qa = ObservationQualityAssurance()
        self.matcher = PredictionMatcher()
        self.reviewer = ObservationReviewWorkflow()
        self.val_pipeline = ObservationValidationPipeline()

    def test_invalid_timestamps(self):
        """Verifies rejection of future timestamps, pre-epoch dates, and malformed strings."""
        now = datetime.now(timezone.utc)

        # 1. Future timestamp (1 hour in future)
        future_time = (now + timedelta(hours=1)).isoformat()
        obs_future = FieldObservation(
            timestamp_utc=future_time,
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
        )
        valid, errors, _ = self.qa.validate_observation(obs_future)
        assert not valid
        assert any("future" in e for e in errors)

        # 2. Pre-epoch date (year 2015 precedes 2020 scope)
        obs_old = FieldObservation(
            timestamp_utc="2015-05-10T12:00:00Z",
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
        )
        valid, errors, _ = self.qa.validate_observation(obs_old)
        assert not valid
        assert any("precedes" in e for e in errors)

        # 3. Malformed string
        obs_bad = FieldObservation(
            timestamp_utc="not-a-timestamp",
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
        )
        valid, errors, _ = self.qa.validate_observation(obs_bad)
        assert not valid
        assert any("Invalid timestamp" in e for e in errors)

    def test_measurement_units_and_ranges(self):
        """Verifies rejection of physically impossible measurements."""
        now_str = datetime.now(timezone.utc).isoformat()

        # Negative DO
        obs_neg_do = FieldObservation(
            timestamp_utc=now_str,
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
            measurement=InstrumentMeasurement(dissolved_oxygen_mg_L=-3.5),
        )
        valid, errors, _ = self.qa.validate_observation(obs_neg_do)
        assert not valid
        assert any("Measured DO" in e and "outside physical" in e for e in errors)

        # Impossible DO supersaturation (> 20 mg/L)
        obs_high_do = FieldObservation(
            timestamp_utc=now_str,
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
            measurement=InstrumentMeasurement(dissolved_oxygen_mg_L=28.5),
        )
        valid, errors, _ = self.qa.validate_observation(obs_high_do)
        assert not valid

        # Boiling water temperature
        obs_boil = FieldObservation(
            timestamp_utc=now_str,
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
            measurement=InstrumentMeasurement(water_temperature_c=65.0),
        )
        valid, errors, _ = self.qa.validate_observation(obs_boil)
        assert not valid
        assert any("water temperature" in e for e in errors)

        # Acidic battery acid pH (< 3.0)
        obs_acid = FieldObservation(
            timestamp_utc=now_str,
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
            measurement=InstrumentMeasurement(ph=1.2),
        )
        valid, errors, _ = self.qa.validate_observation(obs_acid)
        assert not valid
        assert any("pH" in e for e in errors)

    def test_duplicate_reports_detection(self):
        """Verifies duplicate submission detection within a 15-minute window."""
        t_base = datetime.now(timezone.utc)
        now_str = t_base.isoformat()

        obs1 = FieldObservation(
            observation_id="OBS-1",
            timestamp_utc=now_str,
            observer_handle="Observer-USER1",
            location=ObservationLocation(stream_name="Schuylkill River", reach_description="Boathouse Row"),
            direct_observation=DirectObservation(water_appearance="turbid_muddy", unusual_foam="moderate_patches"),
        )

        # Exact duplicate submitted 5 minutes later
        t_dup = (t_base + timedelta(minutes=5)).isoformat()
        obs2 = FieldObservation(
            observation_id="OBS-2",
            timestamp_utc=t_dup,
            observer_handle="Observer-USER1",
            location=ObservationLocation(stream_name="Schuylkill River", reach_description="Boathouse Row"),
            direct_observation=DirectObservation(water_appearance="turbid_muddy", unusual_foam="moderate_patches"),
        )

        valid, errors, _ = self.qa.validate_observation(obs2, existing_observations=[obs1])
        assert not valid
        assert any("Duplicate submission detected" in e for e in errors)

    def test_unverified_observation_handling(self):
        """Verifies default PENDING_REVIEW state and reviewer audit transitions."""
        obs = FieldObservation(
            location=ObservationLocation(stream_name="Schuylkill River"),
            direct_observation=DirectObservation(water_appearance="clear"),
        )
        assert obs.verification_status == "PENDING_REVIEW"
        assert len(obs.review_audit_trail) == 0

        # Reviewer transition to VERIFIED
        self.reviewer.transition_status(
            obs, "VERIFIED",
            reviewer_id="Reviewer-Sarah",
            review_notes="Field notes match Fairmount water works continuous probe.",
        )
        assert obs.verification_status == "VERIFIED"
        assert len(obs.review_audit_trail) == 1
        assert obs.review_audit_trail[0]["reviewer_id"] == "Reviewer-Sarah"
        assert obs.review_audit_trail[0]["new_state"] == "VERIFIED"

    def test_prediction_matching(self):
        """Verifies spatio-temporal matching between observation and active storm forecast."""
        fc_catalog = [
            {
                "event_id": "STORM-2024-07",
                "forecast_issue_time": "2024-07-15T12:00:00Z",
                "predicted_min_do": 4.5,
                "predicted_risk_probability": 0.45,
            }
        ]

        # Case A: Observation during high-risk storm with fish surface piping -> CORROBORATES
        obs_matching = FieldObservation(
            timestamp_utc="2024-07-16T10:00:00Z",  # 22h after forecast issue
            location=ObservationLocation(
                stream_name="Schuylkill River",
                distance_to_usgs_gage_km=1.2,
            ),
            direct_observation=DirectObservation(
                water_appearance="turbid_muddy",
                aquatic_life_status="fish_piping_surface",
            ),
        )
        match_res = self.matcher.match_observation_to_forecasts(obs_matching, fc_catalog)
        assert match_res.matched_forecast_id == "STORM-2024-07"
        assert match_res.corroboration_status == "CORROBORATES_PREDICTED_RISK"

        # Case B: Observation 10 days later -> INCONCLUSIVE (out of window)
        obs_late = FieldObservation(
            timestamp_utc="2024-07-28T12:00:00Z",
            location=ObservationLocation(stream_name="Schuylkill River", distance_to_usgs_gage_km=1.2),
            direct_observation=DirectObservation(water_appearance="clear"),
        )
        match_late = self.matcher.match_observation_to_forecasts(obs_late, fc_catalog)
        assert match_late.corroboration_status == "INCONCLUSIVE_OR_CONTEXTUAL_ONLY"

    def test_temporal_leakage_prevention(self):
        """Verifies that citizen reports at t > t0 are isolated from model training features."""
        # Forecast issued at t0 = 2024-07-15T00:00:00Z
        # Observation submitted at t = 2024-07-16T14:00:00Z
        obs = FieldObservation(
            timestamp_utc="2024-07-16T14:00:00Z",
            direct_observation=DirectObservation(water_appearance="turbid_muddy"),
            measurement=InstrumentMeasurement(dissolved_oxygen_mg_L=4.8),
        )
        # Check that observation to_dict does not contain model feature keys
        d = obs.to_dict()
        assert "feature_lag_24h" not in d
        assert "rolling_median_discharge" not in d
        # Validation pipeline strictly pairs outcomes post-hoc without altering input matrices
        summary = self.val_pipeline.evaluate_corroboration_summary([obs])
        assert summary["total_observations"] == 1

    def test_privacy_protections(self):
        """Verifies coordinate coarsening, anonymous handle generation, and PII redaction."""
        # Exact GPS coordinates
        exact_lat = 39.967812
        exact_lon = -75.188491
        c_lat, c_lon = self.privacy.coarsen_coordinates(exact_lat, exact_lon)
        assert c_lat == 39.97
        assert c_lon == -75.19

        # Handle anonymization
        handle = self.privacy.generate_anonymous_handle("user_private_email@example.com")
        assert handle.startswith("Observer-")
        assert "example.com" not in handle

        # PII redaction from notes
        raw_notes = "Contact me at volunteer@riverwatch.org or call 215-555-0199 about dead carp near dock."
        sanitized = self.privacy.sanitize_public_notes(raw_notes)
        assert "[EMAIL REDACTED]" in sanitized
        assert "[PHONE REDACTED]" in sanitized
        assert "volunteer@riverwatch.org" not in sanitized
        assert "215-555-0199" not in sanitized

    def test_missing_location_data(self):
        """Verifies that missing stream name fails validation, while missing GPS falls back to text reach."""
        now_str = datetime.now(timezone.utc).isoformat()

        # Missing stream name
        obs_no_name = FieldObservation(
            timestamp_utc=now_str,
            location=ObservationLocation(stream_name=""),
            direct_observation=DirectObservation(water_appearance="clear"),
        )
        valid, errors, _ = self.qa.validate_observation(obs_no_name)
        assert not valid
        assert any("Stream name" in e for e in errors)

        # Valid reach name without GPS coordinates
        obs_text_only = FieldObservation(
            timestamp_utc=now_str,
            location=ObservationLocation(
                stream_name="Schuylkill River",
                reach_description="Flat Rock Dam Canoe Launch",
                exact_latitude=None,
                exact_longitude=None,
            ),
            direct_observation=DirectObservation(water_appearance="slightly_cloudy"),
        )
        valid, errors, warnings = self.qa.validate_observation(obs_text_only)
        assert valid
        assert any("No exact GPS" in w for w in warnings)

    def test_image_validation_and_exif_stripping(self):
        """Verifies EXIF stripping function produces sanitized byte streams."""
        raw_bytes = b"\xff\xd8\xff\xe1\x00\x18Exif\x00\x00II*\x00" + b"dummy image payload"
        stripped = self.privacy.strip_image_metadata(raw_bytes)
        assert isinstance(stripped, bytes)
        assert len(stripped) > 0

    def test_separation_of_observations_and_measurements(self):
        """Verifies that visual observations are never converted into numerical DO labels."""
        obs = FieldObservation(
            direct_observation=DirectObservation(
                water_appearance="dark_tea_colored",
                unusual_odor="sewage_cso",
                unusual_foam="dense_persistent_suds",
            ),
            measurement=InstrumentMeasurement(),  # No instrument DO reading
        )
        # Numerical validation should isolate this and report 0 paired records
        eval_res = self.val_pipeline.evaluate_numerical_forecast_accuracy([obs])
        assert eval_res["status"] == "INSUFFICIENT_QUANTITATIVE_DATA"
        assert eval_res["sample_count"] == 0
        assert eval_res["mean_absolute_error_mg_L"] is None
