"""
AquaRehearsal-X - Prediction Matching & Corroboration Engine
Stage 5: Citizen Observation and Prediction Verification System

Connects incoming citizen stream observations with active or historical model predictions.

Scientific & Methodological Constraints:
1. Defensible Spatial Relationship: Observations must lie within the Schuylkill River reach
   (<= 20 km of USGS 01474500 or matching reach naming).
2. Defensible Temporal Relationship: Observation must occur within the forecast evaluation
   window [t_issue, t_issue + 72h].
3. Qualitative Corroboration vs. Quantitative Measurement:
   - Visual cues (odor, foam, color) provide qualitative corroboration, NEVER direct DO values.
   - Citizen observations are NEVER automatically injected as training labels for the ML model.
4. Categorization:
   - CORROBORATES_PREDICTED_RISK: Field signs align with anticipated deoxygenation.
   - CORROBORATES_PREDICTED_SAFE: Normal conditions observed during low-risk window.
   - CONTRADICTS_PREDICTED_RISK: Healthy stream observed despite high-risk forecast.
   - CONTRADICTS_PREDICTED_SAFE: Severe stress/fish mortality observed during 'safe' forecast.
   - INCONCLUSIVE_OR_CONTEXTUAL_ONLY: Insufficient or ambiguous evidence.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from src.field_check.field_observation_schema import FieldObservation, PredictionMatch
from src.config.stage5_settings import (
    SPATIAL_MATCHING_RADIUS_KM,
    TEMPORAL_MATCHING_WINDOW_HOURS,
    CORROBORATION_STATUSES,
)
from src.utils.logger import logger


class PredictionMatcher:
    """Matches field observations with prior model predictions and evaluates corroboration."""

    def __init__(self, spatial_radius_km: float = SPATIAL_MATCHING_RADIUS_KM):
        self.spatial_radius_km = spatial_radius_km

    def match_observation_to_forecasts(
        self,
        observation: FieldObservation,
        forecast_catalog: List[Dict[str, Any]],
    ) -> PredictionMatch:
        """
        Matches a single observation to the most temporally and spatially relevant forecast.

        Args:
            observation: The citizen field observation instance.
            forecast_catalog: List of forecast dicts (containing forecast_issue_time,
                             predicted_min_do, risk_probability, etc.).

        Returns:
            PredictionMatch object populated with match metadata and corroboration status.
        """
        # 1. Spatial Feasibility Check
        dist = observation.location.distance_to_usgs_gage_km
        stream = observation.location.stream_name.lower()
        is_schuylkill = "schuylkill" in stream or "fairmount" in stream or "wissahickon" in stream

        if dist is not None and dist > self.spatial_radius_km:
            return PredictionMatch(
                corroboration_status="INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
                corroboration_explanation=(
                    f"Observation location is {dist:.1f} km from USGS Station 01474500, "
                    f"exceeding the defensible spatial matching threshold ({self.spatial_radius_km} km)."
                ),
            )

        if dist is None and not is_schuylkill:
            return PredictionMatch(
                corroboration_status="INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
                corroboration_explanation="Observation location is outside the Schuylkill River drainage corridor.",
            )

        # 2. Parse Observation Timestamp
        try:
            obs_dt = datetime.fromisoformat(observation.timestamp_utc.replace("Z", "+00:00"))
        except Exception:
            return PredictionMatch(
                corroboration_status="INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
                corroboration_explanation="Invalid observation timestamp; cannot establish temporal alignment.",
            )

        # 3. Find Closest Prior Forecast Window
        best_match = None
        min_time_delta_h = float("inf")

        for fc in forecast_catalog:
            try:
                fc_issue_str = fc.get("forecast_issue_time") or fc.get("event_start")
                if not fc_issue_str:
                    continue
                fc_dt = datetime.fromisoformat(fc_issue_str.replace("Z", "+00:00"))

                # Delta: hours between forecast issue and observation
                delta_h = (obs_dt - fc_dt).total_seconds() / 3600.0

                # Observation must occur within or slightly before/after the 72h forecast horizon (-6h to +78h)
                if -6.0 <= delta_h <= 78.0:
                    if abs(delta_h - 24.0) < min_time_delta_h:  # Favor peak storm response window
                        min_time_delta_h = abs(delta_h - 24.0)
                        best_match = (fc, delta_h)
            except Exception:
                continue

        if not best_match:
            return PredictionMatch(
                corroboration_status="INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
                corroboration_explanation="No active storm forecast was issued within the temporal window of this observation.",
            )

        matched_fc, actual_delta_h = best_match

        # 4. Evaluate Corroboration Logic
        pred_risk = float(matched_fc.get("predicted_risk_probability", matched_fc.get("predicted_risk", 0.10)))
        pred_min_do = matched_fc.get("predicted_min_do", matched_fc.get("expected_min_do_72h", 6.5))

        status, explanation = self._evaluate_corroboration_status(observation, pred_risk, pred_min_do, actual_delta_h)

        return PredictionMatch(
            matched_forecast_id=str(matched_fc.get("event_id", matched_fc.get("forecast_id", "FC-HIST"))),
            forecast_issue_time=matched_fc.get("forecast_issue_time") or matched_fc.get("event_start"),
            forecast_min_do_mg_L=round(pred_min_do, 2) if pred_min_do is not None else None,
            forecast_risk_probability=round(pred_risk, 4),
            time_delta_hours=round(actual_delta_h, 1),
            corroboration_status=status,
            corroboration_explanation=explanation,
        )

    def _evaluate_corroboration_status(
        self,
        obs: FieldObservation,
        pred_risk: float,
        pred_min_do: Optional[float],
        delta_h: float,
    ) -> Tuple[str, str]:
        """Evaluates whether the field observation supports or contradicts the forecast."""
        meas_do = obs.measurement.dissolved_oxygen_mg_L
        wildlife = obs.direct_observation.aquatic_life_status
        appearance = obs.direct_observation.water_appearance
        odor = obs.direct_observation.unusual_odor

        # Stress indicators
        has_fish_mortality = wildlife in ["dead_fish_few_1_5", "dead_fish_moderate_6_20", "dead_fish_large_kill_over_20"]
        has_fish_piping = (wildlife == "fish_piping_surface")
        has_sewage_washoff = (odor in ["sewage_cso", "rotten_egg_sulfur"]) or (appearance in ["dark_tea_colored", "black_anaerobic"])
        has_severe_probe_drop = (meas_do is not None and meas_do < 5.0)

        # Healthy indicators
        has_active_fish = (wildlife == "normal_active_fish")
        has_clear_water = (appearance in ["clear", "slightly_cloudy"]) and (odor == "none")
        has_healthy_probe_do = (meas_do is not None and meas_do >= 6.5)

        is_high_risk_forecast = (pred_risk >= 0.20) or (pred_min_do is not None and pred_min_do < 5.0)

        # Branch 1: Model predicted HIGH RISK of DO depression
        if is_high_risk_forecast:
            if has_severe_probe_drop:
                return (
                    "CORROBORATES_PREDICTED_RISK",
                    f"Measured DO ({meas_do:.2f} mg/L) confirmed threshold crossing predicted by the model (forecast risk: {pred_risk*100:.1f}%).",
                )
            elif has_fish_piping or has_fish_mortality:
                return (
                    "CORROBORATES_PREDICTED_RISK",
                    f"Visual aquatic wildlife stress (status: '{wildlife}') qualitatively corroborates predicted elevated oxygen risk ({pred_risk*100:.1f}%).",
                )
            elif has_sewage_washoff and appearance == "turbid_muddy":
                return (
                    "CORROBORATES_PREDICTED_RISK",
                    f"Visual muddy runoff and CSO odor qualitatively corroborate severe urban wash-off loading.",
                )
            elif has_healthy_probe_do and has_active_fish:
                return (
                    "CONTRADICTS_PREDICTED_RISK",
                    f"Field probe measured healthy DO ({meas_do:.2f} mg/L) and active wildlife despite high-risk forecast ({pred_risk*100:.1f}%). Potential model false alarm.",
                )

        # Branch 2: Model predicted LOW RISK / SAFE conditions
        else:
            if has_fish_mortality or has_severe_probe_drop:
                return (
                    "CONTRADICTS_PREDICTED_SAFE",
                    f"Acute field stress observed (wildlife: '{wildlife}', probe DO: {meas_do} mg/L) despite safe model forecast (risk: {pred_risk*100:.1f}%). Critical model underprediction flag.",
                )
            elif has_clear_water or has_active_fish or has_healthy_probe_do:
                return (
                    "CORROBORATES_PREDICTED_SAFE",
                    f"Normal stream appearance and healthy aquatic life align with low-risk model forecast (risk: {pred_risk*100:.1f}%).",
                )

        # Default fallback
        return (
            "INCONCLUSIVE_OR_CONTEXTUAL_ONLY",
            f"Observation provides qualitative context ({appearance}, odor: {odor}) without conclusive quantitative or biological evidence to evaluate forecast.",
        )
