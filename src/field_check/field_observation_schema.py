"""
AquaRehearsal-X - Field Observation Data Schema
Stage 5: Citizen Observation and Prediction Verification System

Defines structured data schemas separating:
1. Direct sensory observations (visual appearance, foam, odor, wildlife).
2. User interpretations (subjective impressions, non-definitive).
3. Instrument measurements (handheld probes, test strips, temperature).
4. Laboratory-confirmed results (certified EPA/standard methods).
5. Spatiotemporal location and privacy-coarsened coordinates.
6. Verification status and reviewer audit trail.

Scientific Rule:
Never label a stream 'polluted', 'toxic', or 'unsafe' based solely on visual appearance
or olfactory notes. Visual cues provide qualitative context, not quantitative dissolved oxygen data.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid

from src.config.stage5_settings import (
    OBSERVATION_VOCABULARY,
    MEASUREMENT_BOUNDS,
    REVIEW_STATES,
    CORROBORATION_STATUSES,
)


@dataclass
class DirectObservation:
    """Qualitative direct sensory observations (factual field notes)."""
    water_appearance: str = "slightly_cloudy"
    unusual_foam: str = "none"
    unusual_odor: str = "none"
    aquatic_life_status: str = "none_observed"
    visible_discoloration: str = "none"
    recent_weather: str = "dry_clear"
    photo_filename: Optional[str] = None


@dataclass
class UserInterpretation:
    """Observer's subjective interpretation (explicitly segregated from measurements)."""
    perceived_stream_condition: str = "typical_baseline"  # 'typical_baseline', 'mildly_disturbed', 'concerning', 'unknown'
    suspected_cause: Optional[str] = None                 # e.g., 'recent_storm_runoff', 'algal_bloom', 'unknown'
    confidence_level: str = "moderate"                   # 'low', 'moderate', 'high'
    observer_notes: str = ""


@dataclass
class InstrumentMeasurement:
    """Optional quantitative in-situ instrument measurements."""
    dissolved_oxygen_mg_L: Optional[float] = None
    water_temperature_c: Optional[float] = None
    ph: Optional[float] = None
    specific_conductance_us_cm: Optional[float] = None
    instrument_type: Optional[str] = None               # e.g., 'optical_do_probe', 'winkler_titration_kit', 'test_strip'
    probe_calibrated_recently: bool = False
    measurement_notes: Optional[str] = None


@dataclass
class LaboratoryResult:
    """Certified laboratory analysis results (if available)."""
    is_certified_lab: bool = False
    lab_name: Optional[str] = None
    certified_do_mg_L: Optional[float] = None
    biochemical_oxygen_demand_mg_L: Optional[float] = None
    e_coli_mpn_per_100ml: Optional[float] = None
    sample_collection_time: Optional[str] = None
    chain_of_custody_id: Optional[str] = None


@dataclass
class ObservationLocation:
    """Spatial context with public coarsening for privacy protection."""
    stream_name: str = "Schuylkill River"
    reach_description: str = "Schuylkill River near Fairmount Dam / Boathouse Row"
    exact_latitude: Optional[float] = None
    exact_longitude: Optional[float] = None
    public_coarse_latitude: Optional[float] = None
    public_coarse_longitude: Optional[float] = None
    distance_to_usgs_gage_km: Optional[float] = None
    nearest_station_id: str = "01474500"


@dataclass
class PredictionMatch:
    """Linkage between field observation and active/historical model forecast."""
    matched_forecast_id: Optional[str] = None
    forecast_issue_time: Optional[str] = None
    forecast_min_do_mg_L: Optional[float] = None
    forecast_risk_probability: Optional[float] = None
    time_delta_hours: Optional[float] = None
    corroboration_status: str = "INCONCLUSIVE_OR_CONTEXTUAL_ONLY"
    corroboration_explanation: str = "No compatible forecast event within spatial-temporal matching tolerance."


@dataclass
class ReviewAuditEntry:
    """Single state-change entry in the reviewer audit trail."""
    timestamp: str
    reviewer_id: str
    previous_state: str
    new_state: str
    review_notes: str


@dataclass
class FieldObservation:
    """Master record for a citizen science stream observation."""
    observation_id: str = field(default_factory=lambda: f"OBS-{uuid.uuid4().hex[:8].upper()}")
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    observer_handle: str = "Observer-ANON"
    is_synthetic_demonstration: bool = False

    location: ObservationLocation = field(default_factory=ObservationLocation)
    direct_observation: DirectObservation = field(default_factory=DirectObservation)
    interpretation: UserInterpretation = field(default_factory=UserInterpretation)
    measurement: InstrumentMeasurement = field(default_factory=InstrumentMeasurement)
    laboratory: LaboratoryResult = field(default_factory=LaboratoryResult)
    prediction_match: PredictionMatch = field(default_factory=PredictionMatch)

    verification_status: str = "PENDING_REVIEW"
    review_audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the observation record to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldObservation":
        """Reconstructs a FieldObservation instance from a dictionary."""
        loc = ObservationLocation(**data.get("location", {}))
        obs = DirectObservation(**data.get("direct_observation", {}))
        interp = UserInterpretation(**data.get("interpretation", {}))
        meas = InstrumentMeasurement(**data.get("measurement", {}))
        lab = LaboratoryResult(**data.get("laboratory", {}))
        match = PredictionMatch(**data.get("prediction_match", {}))

        return cls(
            observation_id=data.get("observation_id", f"OBS-{uuid.uuid4().hex[:8].upper()}"),
            timestamp_utc=data.get("timestamp_utc", datetime.now(timezone.utc).isoformat()),
            observer_handle=data.get("observer_handle", "Observer-ANON"),
            is_synthetic_demonstration=data.get("is_synthetic_demonstration", False),
            location=loc,
            direct_observation=obs,
            interpretation=interp,
            measurement=meas,
            laboratory=lab,
            prediction_match=match,
            verification_status=data.get("verification_status", "PENDING_REVIEW"),
            review_audit_trail=data.get("review_audit_trail", []),
        )
