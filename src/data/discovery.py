"""
AquaRehearsal-X - Candidate Station Discovery and Evaluation Module
Stage 1: Real Data Foundation

Discovers USGS water monitoring stations, retrieves metadata, evaluates parameter availability,
temporal resolution, and missingness, and produces data/reports/station_candidates.csv
using configurable, transparent numerical criteria.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.config.settings import (
    REPORTS_DIR,
    SUITABILITY_CRITERIA,
    USGS_PARAM_CODES,
)
from src.data.cleaner import DataCleaner
from src.data.resampler import DataResampler
from src.data.usgs_client import USGSClient
from src.utils.logger import logger


class StationEvaluator:
    """Evaluates candidate station data completeness and classifies suitability."""

    def __init__(self, criteria: Optional[Dict[str, Any]] = None):
        self.criteria = criteria or SUITABILITY_CRITERIA

    def evaluate_station(
        self,
        df: pd.DataFrame,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculates data availability, completeness, frequency, and suitability class
        for a single candidate station's time series.
        """
        station_id = metadata.get("station_id", "UNKNOWN")
        station_name = metadata.get("station_name", "UNKNOWN")
        lat = metadata.get("latitude")
        lon = metadata.get("longitude")

        if df.empty:
            return {
                "station_id": station_id,
                "station_name": station_name,
                "latitude": lat,
                "longitude": lon,
                "available_parameters": "NONE",
                "earliest_date": None,
                "latest_date": None,
                "total_observations": 0,
                "temporal_frequency": "unavailable",
                "do_availability_pct": 0.0,
                "temp_availability_pct": 0.0,
                "discharge_availability_pct": 0.0,
                "turbidity_availability_pct": 0.0,
                "missing_pct": 100.0,
                "longest_gap_days": 0.0,
                "suitability_class": "INSUFFICIENT",
                "suitability_reason": "No observations returned from USGS API for requested window.",
            }

        total_obs = len(df)
        earliest_date = df.index.min().isoformat()
        latest_date = df.index.max().isoformat()

        # Detect native temporal resolution
        res_info = DataResampler.detect_native_resolution(df)
        freq_str = res_info["native_frequency"]

        # Calculate max continuous gap in days
        deltas = df.index.to_series().diff().dropna()
        longest_gap_days = (
            round(deltas.max().total_seconds() / 86400.0, 2) if not deltas.empty else 0.0
        )

        # Calculate parameter-specific valid observation percentages
        has_do = "dissolved_oxygen" in df.columns
        has_temp = "water_temperature" in df.columns
        has_q = "discharge" in df.columns
        has_turb = "turbidity" in df.columns

        do_pct = round(100.0 * df["dissolved_oxygen"].notna().sum() / total_obs, 2) if has_do else 0.0
        temp_pct = round(100.0 * df["water_temperature"].notna().sum() / total_obs, 2) if has_temp else 0.0
        q_pct = round(100.0 * df["discharge"].notna().sum() / total_obs, 2) if has_q else 0.0
        turb_pct = round(100.0 * df["turbidity"].notna().sum() / total_obs, 2) if has_turb else 0.0

        # General missing percentage across primary 3 variables
        primary_cols = [c for c in ["dissolved_oxygen", "water_temperature", "discharge"] if c in df.columns]
        if primary_cols:
            all_missing = df[primary_cols].isna().all(axis=1).sum()
            general_missing_pct = round(100.0 * all_missing / total_obs, 2)
        else:
            general_missing_pct = 100.0

        # Determine suitability according to configured criteria
        good = self.criteria.get("good", {})
        warn = self.criteria.get("warning", {})

        suitability = "INSUFFICIENT"
        reasons = []

        if not has_do or do_pct < warn.get("min_do_availability_pct", 50.0):
            suitability = "INSUFFICIENT"
            reasons.append(f"DO availability ({do_pct}%) is below minimum threshold ({warn.get('min_do_availability_pct')}%)")
        elif not has_q or q_pct < warn.get("min_discharge_availability_pct", 40.0):
            suitability = "INSUFFICIENT"
            reasons.append(f"Discharge availability ({q_pct}%) is below warning threshold ({warn.get('min_discharge_availability_pct')}%)")
        else:
            # Check for GOOD classification
            is_good = (
                do_pct >= good.get("min_do_availability_pct", 80.0)
                and temp_pct >= good.get("min_temp_availability_pct", 75.0)
                and q_pct >= good.get("min_discharge_availability_pct", 70.0)
                and longest_gap_days <= good.get("max_continuous_gap_days", 14.0)
                and total_obs >= good.get("min_observations", 5000)
            )

            if is_good:
                suitability = "GOOD"
                reasons.append(
                    f"Meets all GOOD thresholds: DO={do_pct}%, Temp={temp_pct}%, "
                    f"Discharge={q_pct}%, MaxGap={longest_gap_days}d, Obs={total_obs}"
                )
            else:
                suitability = "WARNING"
                reasons.append(
                    f"Passed minimum thresholds but missed GOOD criteria: DO={do_pct}%, "
                    f"Temp={temp_pct}%, Discharge={q_pct}%, MaxGap={longest_gap_days}d, Obs={total_obs}"
                )

        avail_params = list(metadata.get("available_parameters", {}).keys())
        param_str = ";".join(avail_params) if avail_params else "UNKNOWN"

        eval_summary = {
            "station_id": station_id,
            "station_name": station_name,
            "latitude": lat,
            "longitude": lon,
            "available_parameters": param_str,
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "total_observations": total_obs,
            "temporal_frequency": freq_str,
            "do_availability_pct": do_pct,
            "temp_availability_pct": temp_pct,
            "discharge_availability_pct": q_pct,
            "turbidity_availability_pct": turb_pct,
            "missing_pct": general_missing_pct,
            "longest_gap_days": longest_gap_days,
            "suitability_class": suitability,
            "suitability_reason": " | ".join(reasons),
        }
        return eval_summary


class StationDiscovery:
    """Discovers and catalogs candidate stations for AquaRehearsal-X."""

    def __init__(self, client: Optional[USGSClient] = None):
        self.client = client or USGSClient()
        self.cleaner = DataCleaner()
        self.evaluator = StationEvaluator()

    def discover_and_evaluate_candidates(
        self,
        candidate_site_ids: List[str],
        start_date: str,
        end_date: str,
        save_report: bool = True,
    ) -> pd.DataFrame:
        """
        Evaluates a list of candidate stations against the real USGS API.
        Produces and writes data/reports/station_candidates.csv.
        """
        results = []

        for site_id in candidate_site_ids:
            logger.info("Evaluating candidate station: %s", site_id)
            try:
                raw_payload = self.client.fetch_iv_data(
                    site_id=site_id,
                    start_date=start_date,
                    end_date=end_date,
                )
                df, metadata = self.client.parse_iv_response(raw_payload)
                if not df.empty:
                    df, _ = self.cleaner.clean_timeseries(df, station_id=site_id)

                summary = self.evaluator.evaluate_station(df, metadata)
                results.append(summary)
            except Exception as e:
                logger.error("Failed to evaluate station %s: %s", site_id, e)
                results.append({
                    "station_id": site_id,
                    "station_name": "API_ERROR",
                    "latitude": None,
                    "longitude": None,
                    "available_parameters": "ERROR",
                    "earliest_date": None,
                    "latest_date": None,
                    "total_observations": 0,
                    "temporal_frequency": "unavailable",
                    "do_availability_pct": 0.0,
                    "temp_availability_pct": 0.0,
                    "discharge_availability_pct": 0.0,
                    "turbidity_availability_pct": 0.0,
                    "missing_pct": 100.0,
                    "longest_gap_days": 0.0,
                    "suitability_class": "INSUFFICIENT",
                    "suitability_reason": f"USGS API error: {str(e)}",
                })

        candidates_df = pd.DataFrame(results)

        if save_report:
            out_file = REPORTS_DIR / "station_candidates.csv"
            candidates_df.to_csv(out_file, index=False)
            logger.info("Saved station candidate report to %s", out_file)

        return candidates_df
