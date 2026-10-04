"""
AquaRehearsal-X - Observation Quality Assurance & Validation Rules
Stage 5: Citizen Observation and Prediction Verification System

Enforces observation-quality safeguards:
1. Required fields and controlled vocabulary adherence.
2. Temporal sanity checks (no future timestamps, no pre-epoch dates).
3. Physical measurement unit and range validation (DO, water temp, pH).
4. Spatial boundary verification (Schuylkill watershed bounds check & Haversine distance).
5. Duplicate report detection (15-minute spatio-temporal hash collision).
6. Basic spam, abuse, and text sanitization.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import math
import hashlib

from src.config.stage5_settings import (
    SCHUYLKILL_BOUNDS,
    STATION_COORDINATES,
    MEASUREMENT_BOUNDS,
    OBSERVATION_VOCABULARY,
)
from src.field_check.field_observation_schema import FieldObservation


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class ObservationQualityAssurance:
    """Enforces rigorous QA/QC rules on incoming citizen stream observations."""

    def __init__(self):
        self.submission_cache: Dict[str, datetime] = {}

    def validate_observation(
        self,
        observation: FieldObservation,
        existing_observations: Optional[List[FieldObservation]] = None,
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validates an incoming observation record.

        Returns:
            Tuple of (is_valid: bool, fatal_errors: List[str], quality_warnings: List[str])
        """
        fatal_errors = []
        warnings = []

        # 1. Required Fields Check
        if not observation.location.stream_name.strip():
            fatal_errors.append("Stream name or location description is required.")
        if not observation.direct_observation.water_appearance:
            fatal_errors.append("Water appearance observation is required.")

        # 2. Timestamp Validation
        try:
            obs_time = datetime.fromisoformat(observation.timestamp_utc.replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            # Allow max 5 minutes for client clock skew
            if obs_time > now_utc and (obs_time - now_utc).total_seconds() > 300:
                fatal_errors.append(f"Observation timestamp ({observation.timestamp_utc}) cannot be in the future.")
            if obs_time.year < 2020:
                fatal_errors.append("Observation timestamp precedes platform operational scope (2020).")
        except Exception as e:
            fatal_errors.append(f"Invalid timestamp format: {e}")
            obs_time = None

        # 3. Controlled Vocabulary Compliance
        for field_name, allowed_vals in OBSERVATION_VOCABULARY.items():
            val = getattr(observation.direct_observation, field_name, None)
            if val and val not in allowed_vals:
                warnings.append(f"Field '{field_name}' value '{val}' not in standard vocabulary.")

        # 4. Spatial Bounds & Haversine Distance
        lat = observation.location.exact_latitude
        lon = observation.location.exact_longitude
        if lat is not None and lon is not None:
            if not (
                SCHUYLKILL_BOUNDS["min_latitude"] <= lat <= SCHUYLKILL_BOUNDS["max_latitude"]
                and SCHUYLKILL_BOUNDS["min_longitude"] <= lon <= SCHUYLKILL_BOUNDS["max_longitude"]
            ):
                warnings.append(
                    f"Coordinates ({lat:.4f}, {lon:.4f}) fall outside Schuylkill River watershed bounding box."
                )

            # Compute distance to USGS gage 01474500
            dist = haversine_distance_km(
                lat, lon,
                STATION_COORDINATES["latitude"], STATION_COORDINATES["longitude"]
            )
            observation.location.distance_to_usgs_gage_km = round(dist, 2)
        else:
            warnings.append("No exact GPS coordinates provided; relying on textual reach description.")

        # 5. Quantitative Measurement Unit & Physical Bounds Check
        meas = observation.measurement
        if meas.dissolved_oxygen_mg_L is not None:
            do_val = meas.dissolved_oxygen_mg_L
            bounds = MEASUREMENT_BOUNDS["dissolved_oxygen_mg_L"]
            if do_val < bounds["min"] or do_val > bounds["max"]:
                fatal_errors.append(
                    f"Measured DO ({do_val} mg/L) falls outside physical aquatic limits [{bounds['min']}, {bounds['max']}]."
                )

        if meas.water_temperature_c is not None:
            temp_val = meas.water_temperature_c
            bounds = MEASUREMENT_BOUNDS["water_temperature_c"]
            if temp_val < bounds["min"] or temp_val > bounds["max"]:
                fatal_errors.append(
                    f"Measured water temperature ({temp_val}°C) falls outside physical liquid bounds [{bounds['min']}, {bounds['max']}]."
                )

        if meas.ph is not None:
            ph_val = meas.ph
            bounds = MEASUREMENT_BOUNDS["ph"]
            if ph_val < bounds["min"] or ph_val > bounds["max"]:
                fatal_errors.append(f"Measured pH ({ph_val}) falls outside physical bounds [{bounds['min']}, {bounds['max']}].")

        # 6. Duplicate Submission Detection (15-Minute Window)
        if existing_observations and obs_time:
            obs_hash = self._generate_duplicate_fingerprint(observation)
            for ex in existing_observations:
                if ex.observation_id == observation.observation_id:
                    continue
                try:
                    ex_time = datetime.fromisoformat(ex.timestamp_utc.replace("Z", "+00:00"))
                    ex_hash = self._generate_duplicate_fingerprint(ex)
                    if obs_hash == ex_hash and abs((obs_time - ex_time).total_seconds()) < 900:
                        fatal_errors.append(f"Duplicate submission detected: identical report received within 15 minutes (matches {ex.observation_id}).")
                        break
                except Exception:
                    pass

        # 7. Spam & Content Abuse Protection
        notes = observation.interpretation.observer_notes
        if notes:
            if len(notes) > 2000:
                fatal_errors.append("Observer notes exceed maximum length limit (2000 characters).")
            # Simple spam check (excessive URLs)
            if notes.count("http://") + notes.count("https://") > 2:
                fatal_errors.append("Observer notes contain excessive external web links (flagged as spam).")

        is_valid = (len(fatal_errors) == 0)
        return is_valid, fatal_errors, warnings

    def _generate_duplicate_fingerprint(self, obs: FieldObservation) -> str:
        """Generates a coarse fingerprint of observer and content to catch duplicate submissions."""
        handle = obs.observer_handle.strip().lower()
        reach = obs.location.reach_description.strip().lower()
        content_key = f"{obs.direct_observation.water_appearance}-{obs.direct_observation.unusual_foam}"
        raw = f"{handle}|{reach}|{content_key}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
