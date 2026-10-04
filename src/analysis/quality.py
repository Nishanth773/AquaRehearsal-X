"""
AquaRehearsal-X - Data Quality Reporting Module
Stage 1: Real Data Foundation

Computes detailed completeness, gap structure, and multi-variable co-occurrence
statistics across candidate monitoring stations, exporting data/reports/data_quality_report.csv.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config.settings import REPORTS_DIR
from src.data.resampler import DataResampler
from src.utils.logger import logger


class DataQualityAnalyzer:
    """Performs rigorous missingness, gap, and multi-sensor alignment analysis."""

    def evaluate_quality(
        self,
        station_id: str,
        df: pd.DataFrame,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculates deep quality metrics for a single station's time series."""
        if df.empty:
            return {
                "station_id": station_id,
                "station_name": metadata.get("station_name", "UNKNOWN"),
                "date_range_start": None,
                "date_range_end": None,
                "total_observations": 0,
                "temporal_frequency": "unavailable",
                "missing_pct_grid": 100.0,
                "longest_continuous_gap_days": 0.0,
                "do_pct": 0.0,
                "temp_pct": 0.0,
                "discharge_pct": 0.0,
                "turbidity_pct": 0.0,
                "do_and_discharge_cooccurrence_pct": 0.0,
                "do_temp_discharge_cooccurrence_pct": 0.0,
            }

        total_obs = len(df)
        start_dt = df.index.min()
        end_dt = df.index.max()

        res_info = DataResampler.detect_native_resolution(df)
        freq_str = res_info["native_frequency"]
        median_minutes = res_info.get("median_interval_minutes") or 15.0

        # Calculate expected observations based on median interval
        span_minutes = (end_dt - start_dt).total_seconds() / 60.0
        expected_obs = int(span_minutes / max(median_minutes, 1.0)) + 1
        missing_grid_pct = round(max(0.0, (1.0 - (total_obs / max(expected_obs, 1)))) * 100.0, 2)

        # Longest gap
        deltas = df.index.to_series().diff().dropna()
        max_gap_days = (
            round(deltas.max().total_seconds() / 86400.0, 2) if not deltas.empty else 0.0
        )

        # Parameter percentages
        has_do = "dissolved_oxygen" in df.columns
        has_temp = "water_temperature" in df.columns
        has_q = "discharge" in df.columns
        has_turb = "turbidity" in df.columns

        do_valid = df["dissolved_oxygen"].notna() if has_do else pd.Series(False, index=df.index)
        temp_valid = df["water_temperature"].notna() if has_temp else pd.Series(False, index=df.index)
        q_valid = df["discharge"].notna() if has_q else pd.Series(False, index=df.index)
        turb_valid = df["turbidity"].notna() if has_turb else pd.Series(False, index=df.index)

        do_pct = round(100.0 * do_valid.sum() / total_obs, 2)
        temp_pct = round(100.0 * temp_valid.sum() / total_obs, 2)
        q_pct = round(100.0 * q_valid.sum() / total_obs, 2)
        turb_pct = round(100.0 * turb_valid.sum() / total_obs, 2)

        # Co-occurrence analysis (crucial for physical models)
        do_and_q = (do_valid & q_valid).sum()
        do_and_q_pct = round(100.0 * do_and_q / total_obs, 2)

        primary_cooccur = (do_valid & temp_valid & q_valid).sum()
        primary_cooccur_pct = round(100.0 * primary_cooccur / total_obs, 2)

        return {
            "station_id": station_id,
            "station_name": metadata.get("station_name", "UNKNOWN"),
            "date_range_start": start_dt.isoformat(),
            "date_range_end": end_dt.isoformat(),
            "total_observations": total_obs,
            "temporal_frequency": freq_str,
            "missing_pct_grid": missing_grid_pct,
            "longest_continuous_gap_days": max_gap_days,
            "do_pct": do_pct,
            "temp_pct": temp_pct,
            "discharge_pct": q_pct,
            "turbidity_pct": turb_pct,
            "do_and_discharge_cooccurrence_pct": do_and_q_pct,
            "do_temp_discharge_cooccurrence_pct": primary_cooccur_pct,
        }

    def generate_quality_report(
        self,
        station_data: Dict[str, Tuple[pd.DataFrame, Dict[str, Any]]],
        save_csv: bool = True,
    ) -> pd.DataFrame:
        """Generates cross-station quality report and exports to CSV."""
        rows = []
        for station_id, (df, meta) in station_data.items():
            report_row = self.evaluate_quality(station_id, df, meta)
            rows.append(report_row)

        report_df = pd.DataFrame(rows)
        if save_csv:
            out_path = REPORTS_DIR / "data_quality_report.csv"
            report_df.to_csv(out_path, index=False)
            logger.info("Saved data quality report to %s", out_path)

        return report_df
