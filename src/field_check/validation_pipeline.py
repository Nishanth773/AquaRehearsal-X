"""
AquaRehearsal-X - Observation-to-Validation Closed Loop Pipeline
Stage 5: Citizen Observation and Prediction Verification System

Integrates citizen observations with continuous sensor measurements for model verification:
1. Stores predictions and associated issue timestamps.
2. Matches against compatible ground observations and verified instrument readings.
3. Strict Leakage Prevention: Field observations recorded post-t0 are strictly segregated
   from feature engineering pipelines.
4. Separates numerical DO error metrics (evaluated ONLY against certified sensors / lab tests)
   from qualitative citizen corroboration rates.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.field_check.field_observation_schema import FieldObservation
from src.utils.logger import logger


class ObservationValidationPipeline:
    """Manages the verification loop between model predictions and ground-truth observations."""

    def __init__(self, target_threshold_mg_L: float = 5.0):
        self.threshold = target_threshold_mg_L

    def evaluate_corroboration_summary(
        self,
        observations: List[FieldObservation],
    ) -> Dict[str, Any]:
        """
        Computes summary statistics of citizen corroboration across historical predictions.
        """
        total = len(observations)
        if total == 0:
            return {
                "total_observations": 0,
                "verified_count": 0,
                "corroborated_count": 0,
                "contradicted_count": 0,
                "inconclusive_count": 0,
                "corroboration_rate_pct": 0.0,
                "status_breakdown": {},
                "corroboration_breakdown": {},
            }

        verified = [obs for obs in observations if obs.verification_status == "VERIFIED"]
        
        status_counts = {}
        for obs in observations:
            st = obs.verification_status
            status_counts[st] = status_counts.get(st, 0) + 1

        corroboration_counts = {}
        corroborated_pos = 0
        contradicted_pos = 0
        inconclusive_pos = 0

        for obs in observations:
            c_status = obs.prediction_match.corroboration_status
            corroboration_counts[c_status] = corroboration_counts.get(c_status, 0) + 1

            if "CORROBORATES" in c_status:
                corroborated_pos += 1
            elif "CONTRADICTS" in c_status:
                contradicted_pos += 1
            else:
                inconclusive_pos += 1

        corrob_rate = (corroborated_pos / total) * 100.0 if total > 0 else 0.0

        return {
            "total_observations": total,
            "verified_count": len(verified),
            "unverified_pending_count": status_counts.get("PENDING_REVIEW", 0),
            "corroborated_count": corroborated_pos,
            "contradicted_count": contradicted_pos,
            "inconclusive_count": inconclusive_pos,
            "corroboration_rate_pct": round(corrob_rate, 1),
            "status_breakdown": status_counts,
            "corroboration_breakdown": corroboration_counts,
        }

    def evaluate_numerical_forecast_accuracy(
        self,
        observations: List[FieldObservation],
        certified_sensor_reference_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates numerical accuracy strictly using instrument measurements
        and certified USGS gage readings, NOT visual appearance.
        """
        paired_errors = []
        for obs in observations:
            # Only use verified instrument measurements
            meas_do = obs.measurement.dissolved_oxygen_mg_L
            pred_do = obs.prediction_match.forecast_min_do_mg_L

            if meas_do is not None and pred_do is not None and obs.verification_status == "VERIFIED":
                paired_errors.append({
                    "observation_id": obs.observation_id,
                    "measured_do": meas_do,
                    "predicted_do": pred_do,
                    "error": pred_do - meas_do,
                })

        if not paired_errors:
            return {
                "status": "INSUFFICIENT_QUANTITATIVE_DATA",
                "message": "No verified instrument measurements paired with predictions yet.",
                "sample_count": 0,
                "mean_absolute_error_mg_L": None,
                "root_mean_squared_error_mg_L": None,
            }

        df_err = pd.DataFrame(paired_errors)
        mae = float(np.mean(np.abs(df_err["error"])))
        rmse = float(np.sqrt(np.mean(df_err["error"] ** 2)))

        return {
            "status": "VALIDATED_NUMERICAL_SAMPLE",
            "sample_count": len(df_err),
            "mean_absolute_error_mg_L": round(mae, 3),
            "root_mean_squared_error_mg_L": round(rmse, 3),
            "paired_records": paired_errors,
        }
