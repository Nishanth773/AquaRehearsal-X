"""
AquaRehearsal-X - Observation Submission & Persistence Repository
Stage 5: Citizen Observation and Prediction Verification System

Manages the lifecycle of field observations:
1. Intake, validation, and privacy coarsening.
2. Forecast matching against historical and active prediction catalogs.
3. Storage persistence in data/reports/stage5/field_observations.json.
4. Separate seeding of clearly labeled demonstration fixtures (is_synthetic_demonstration = True)
   to ensure zero fabrication in real monitoring records.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime, timezone

from src.field_check.field_observation_schema import FieldObservation
from src.field_check.privacy_controls import PrivacyController
from src.field_check.observation_quality import ObservationQualityAssurance
from src.field_check.prediction_matching import PredictionMatcher
from src.config.stage5_settings import STAGE5_REPORTS_DIR
from src.utils.logger import logger


class ObservationRepository:
    """Manages persistence, querying, and intake of citizen stream observations."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        forecast_catalog: Optional[List[Dict[str, Any]]] = None,
    ):
        self.storage_path = storage_path or (STAGE5_REPORTS_DIR / "field_observations.json")
        self.forecast_catalog = forecast_catalog or []

        self.privacy = PrivacyController()
        self.qa = ObservationQualityAssurance()
        self.matcher = PredictionMatcher()

        self._observations: List[FieldObservation] = []
        self._load()

    def _load(self):
        """Loads observations from JSON storage file if it exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._observations = [FieldObservation.from_dict(d) for d in data]
                logger.info("Loaded %d field observations from %s", len(self._observations), self.storage_path)
            except Exception as e:
                logger.warning("Could not read %s: %s. Starting with empty store.", self.storage_path, e)
                self._observations = []
        else:
            self._observations = []

    def save(self):
        """Persists all observations to JSON storage."""
        data = [obs.to_dict() for obs in self._observations]
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved %d field observations to %s", len(self._observations), self.storage_path)

    def submit_observation(
        self,
        raw_data: Dict[str, Any],
        user_identifier: Optional[str] = None,
    ) -> Tuple[bool, Optional[FieldObservation], List[str], List[str]]:
        """
        Processes an incoming field observation through QA, privacy sanitization, and forecast matching.

        Returns:
            Tuple of (success: bool, observation: Optional[FieldObservation], fatal_errors: List[str], warnings: List[str])
        """
        # 1. Instantiate observation from dictionary
        try:
            obs = FieldObservation.from_dict(raw_data)
        except Exception as e:
            return False, None, [f"Invalid observation structure: {e}"], []

        # 2. Apply Privacy Protections
        # Coarsen public coordinates
        c_lat, c_lon = self.privacy.coarsen_coordinates(
            obs.location.exact_latitude, obs.location.exact_longitude
        )
        obs.location.public_coarse_latitude = c_lat
        obs.location.public_coarse_longitude = c_lon

        # Anonymize handle if default
        if obs.observer_handle == "Observer-ANON":
            obs.observer_handle = self.privacy.generate_anonymous_handle(user_identifier)

        # Sanitize text notes
        obs.interpretation.observer_notes = self.privacy.sanitize_public_notes(
            obs.interpretation.observer_notes
        )

        # 3. Quality Assurance Validation
        is_valid, fatal_errors, warnings = self.qa.validate_observation(obs, self._observations)
        if not is_valid:
            return False, obs, fatal_errors, warnings

        # 4. Spatio-temporal Forecast Matching
        if self.forecast_catalog:
            obs.prediction_match = self.matcher.match_observation_to_forecasts(obs, self.forecast_catalog)

        # 5. Persist
        self._observations.append(obs)
        self.save()

        logger.info("Successfully ingested observation %s (status: %s)", obs.observation_id, obs.verification_status)
        return True, obs, [], warnings

    def get_all(self, include_synthetic: bool = True) -> List[FieldObservation]:
        """Returns all observations."""
        if include_synthetic:
            return list(self._observations)
        return [obs for obs in self._observations if not obs.is_synthetic_demonstration]

    def get_by_id(self, obs_id: str) -> Optional[FieldObservation]:
        """Retrieves observation by unique ID."""
        for obs in self._observations:
            if obs.observation_id == obs_id:
                return obs
        return None

    def seed_demo_observations(self):
        """
        Seeds clearly labeled demonstration records for UI rehearsal and automated testing.
        Strictly labeled with is_synthetic_demonstration = True.
        """
        demo_records = [
            {
                "observation_id": "OBS-DEMO-001",
                "timestamp_utc": "2024-07-16T18:30:00Z",
                "observer_handle": "Observer-3F1A",
                "is_synthetic_demonstration": True,
                "verification_status": "VERIFIED",
                "location": {
                    "stream_name": "Schuylkill River",
                    "reach_description": "Fairmount Park Boathouse Row",
                    "exact_latitude": 39.9702,
                    "exact_longitude": -75.1895,
                    "public_coarse_latitude": 39.97,
                    "public_coarse_longitude": -75.19,
                    "distance_to_usgs_gage_km": 0.35,
                    "nearest_station_id": "01474500",
                },
                "direct_observation": {
                    "water_appearance": "turbid_muddy",
                    "unusual_foam": "moderate_patches",
                    "unusual_odor": "sewage_cso",
                    "aquatic_life_status": "fish_piping_surface",
                    "visible_discoloration": "brown_sediment",
                    "recent_weather": "heavy_downpour",
                },
                "interpretation": {
                    "perceived_stream_condition": "concerning",
                    "suspected_cause": "recent_storm_runoff",
                    "confidence_level": "high",
                    "observer_notes": "Heavy stormwater runoff observed following the 40mm summer cloudburst. Multiple small bass piping at the water surface near the dock.",
                },
                "measurement": {
                    "dissolved_oxygen_mg_L": 4.85,
                    "water_temperature_c": 26.2,
                    "ph": 7.4,
                    "specific_conductance_us_cm": 380.0,
                    "instrument_type": "optical_do_probe",
                    "probe_calibrated_recently": True,
                    "measurement_notes": "Calibrated YSI ProDSS optical DO probe.",
                },
                "prediction_match": {
                    "matched_forecast_id": "STORM-2024-07-15",
                    "forecast_issue_time": "2024-07-15T12:00:00Z",
                    "forecast_min_do_mg_L": 4.65,
                    "forecast_risk_probability": 0.42,
                    "time_delta_hours": 30.5,
                    "corroboration_status": "CORROBORATES_PREDICTED_RISK",
                    "corroboration_explanation": "Measured DO (4.85 mg/L) and visual fish surface piping corroborate predicted elevated deoxygenation risk.",
                },
                "review_audit_trail": [
                    {
                        "timestamp": "2024-07-17T09:00:00Z",
                        "reviewer_id": "Dr. Sarah Jenkins (Aquatic Ecologist)",
                        "previous_state": "PENDING_REVIEW",
                        "new_state": "VERIFIED",
                        "review_notes": "Calibrated optical probe reading matches Fairmount Gage discharge crest. Plausible acute summer deoxygenation event.",
                    }
                ],
            },
            {
                "observation_id": "OBS-DEMO-002",
                "timestamp_utc": "2024-05-10T14:15:00Z",
                "observer_handle": "Observer-8B4C",
                "is_synthetic_demonstration": True,
                "verification_status": "VERIFIED",
                "location": {
                    "stream_name": "Schuylkill River",
                    "reach_description": "Schuylkill Banks Boardwalk",
                    "exact_latitude": 39.9521,
                    "exact_longitude": -75.1812,
                    "public_coarse_latitude": 39.95,
                    "public_coarse_longitude": -75.18,
                    "distance_to_usgs_gage_km": 1.85,
                    "nearest_station_id": "01474500",
                },
                "direct_observation": {
                    "water_appearance": "clear",
                    "unusual_foam": "none",
                    "unusual_odor": "none",
                    "aquatic_life_status": "normal_active_fish",
                    "visible_discoloration": "none",
                    "recent_weather": "dry_clear",
                },
                "interpretation": {
                    "perceived_stream_condition": "typical_baseline",
                    "suspected_cause": "none",
                    "confidence_level": "high",
                    "observer_notes": "Water is clear with active carp and sunfish visible near the shoreline. Normal spring conditions.",
                },
                "measurement": {
                    "dissolved_oxygen_mg_L": 8.7,
                    "water_temperature_c": 16.5,
                    "ph": 7.8,
                    "instrument_type": "handheld_probe",
                    "probe_calibrated_recently": True,
                },
                "prediction_match": {
                    "matched_forecast_id": "STORM-2024-05-09",
                    "forecast_issue_time": "2024-05-09T00:00:00Z",
                    "forecast_min_do_mg_L": 8.2,
                    "forecast_risk_probability": 0.02,
                    "time_delta_hours": 38.2,
                    "corroboration_status": "CORROBORATES_PREDICTED_SAFE",
                    "corroboration_explanation": "Measured DO (8.7 mg/L) and active wildlife corroborate safe forecast prediction.",
                },
                "review_audit_trail": [
                    {
                        "timestamp": "2024-05-11T10:00:00Z",
                        "reviewer_id": "Marcus Vance (Hydrologist)",
                        "previous_state": "PENDING_REVIEW",
                        "new_state": "VERIFIED",
                        "review_notes": "Consistent with baseflow USGS gage readings.",
                    }
                ],
            },
            {
                "observation_id": "OBS-DEMO-003",
                "timestamp_utc": "2024-08-22T08:00:00Z",
                "observer_handle": "Observer-99D2",
                "is_synthetic_demonstration": True,
                "verification_status": "PENDING_REVIEW",
                "location": {
                    "stream_name": "Schuylkill River",
                    "reach_description": "Manayunk Canal Towpath",
                    "exact_latitude": 40.0245,
                    "exact_longitude": -75.2230,
                    "public_coarse_latitude": 40.02,
                    "public_coarse_longitude": -75.22,
                    "distance_to_usgs_gage_km": 7.1,
                    "nearest_station_id": "01474500",
                },
                "direct_observation": {
                    "water_appearance": "green_algal",
                    "unusual_foam": "light_flecks",
                    "unusual_odor": "earthy_musty",
                    "aquatic_life_status": "none_observed",
                    "visible_discoloration": "bright_green_bloom",
                    "recent_weather": "prolonged_dry_spell",
                },
                "interpretation": {
                    "perceived_stream_condition": "mildly_disturbed",
                    "suspected_cause": "algal_bloom",
                    "confidence_level": "moderate",
                    "observer_notes": "Slow-moving canal water shows surface green film during late summer dry spell.",
                },
                "measurement": {},
                "prediction_match": {
                    "corroboration_status": "INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
                    "corroboration_explanation": "Visual algal film noted during dry spell; lacks instrument DO reading to confirm supersaturation or nighttime nadir.",
                },
                "review_audit_trail": [],
            },
        ]

        # Ingest demo fixtures if not already present
        existing_ids = {obs.observation_id for obs in self._observations}
        added = 0
        for rec in demo_records:
            if rec["observation_id"] not in existing_ids:
                self._observations.append(FieldObservation.from_dict(rec))
                added += 1

        if added > 0:
            self.save()
            logger.info("Seeded %d synthetic demonstration records to %s", added, self.storage_path)
