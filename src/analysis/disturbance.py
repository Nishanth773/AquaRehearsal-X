"""
AquaRehearsal-X - Candidate Hydrologic Disturbance Event Identification
Stage 1: Real Data Foundation

Identifies candidate storm-triggered hydrologic disturbance events based on observed
stream discharge surges, calculating accompanying water quality sensor responses.

Scientific Integrity:
- Events are labeled strictly as 'CANDIDATE HYDROLOGIC DISTURBANCE EVENTS'
- No fabricated DO collapse or ecological failure thresholds are applied
- Missing responses are preserved explicitly as NaN
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.config.settings import DISTURBANCE_CONFIG, REPORTS_DIR
from src.utils.logger import logger


class DisturbanceDetector:
    """Detects and characterizes hydrologic disturbance events from real sensor data."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or DISTURBANCE_CONFIG

    def detect_candidate_events(
        self,
        df: pd.DataFrame,
        station_id: str,
        save_csv: bool = True,
    ) -> pd.DataFrame:
        """
        Scans time-series data for significant discharge surges and characterizes
        the accompanying DO, temperature, and turbidity dynamics.
        """
        if df.empty or "discharge" not in df.columns:
            logger.warning("No discharge data available for disturbance detection at station %s", station_id)
            return pd.DataFrame()

        q = df["discharge"].dropna()
        if len(q) < 50:
            logger.warning("Insufficient discharge data points for disturbance detection at %s", station_id)
            return pd.DataFrame()

        # Config parameters
        spike_multiplier = self.config.get("discharge_spike_multiplier", 2.5)
        quantile_thresh = self.config.get("discharge_quantile_threshold", 0.90)
        separation_hours = self.config.get("min_event_separation_hours", 36)
        pre_hours = self.config.get("pre_event_window_hours", 24)
        post_hours = self.config.get("post_event_window_hours", 72)

        # Baseline: 7-day rolling median discharge
        rolling_baseline = q.rolling("7D", min_periods=24).median()
        q_threshold_val = float(q.quantile(quantile_thresh))

        # Condition for candidate disturbance: exceeds rolling baseline by multiplier AND exceeds quantile threshold
        is_candidate_surge = (q >= rolling_baseline * spike_multiplier) & (q >= q_threshold_val)

        if not is_candidate_surge.any():
            logger.info("No discharge surges met the candidate criteria for station %s", station_id)
            return pd.DataFrame()

        # Group contiguous surges and find distinct peaks separated by separation_hours
        surge_times = q[is_candidate_surge].index
        events: List[Dict[str, Any]] = []
        last_event_time = None

        # Iterate over peaks
        for t in surge_times:
            if last_event_time is not None:
                diff_hours = (t - last_event_time).total_seconds() / 3600.0
                if diff_hours < separation_hours:
                    continue

            # Look within a local window [t - 12h, t + 24h] to find exact peak discharge
            win_start = t - pd.Timedelta(hours=12)
            win_end = t + pd.Timedelta(hours=24)
            local_q = q.loc[win_start:win_end]
            if local_q.empty:
                continue

            peak_time = local_q.idxmax()
            peak_discharge = float(local_q.max())

            # Identify event start (point where discharge began rising above baseline)
            lookback_start = peak_time - pd.Timedelta(hours=pre_hours)
            pre_series = q.loc[lookback_start:peak_time]
            baseline_val = rolling_baseline.loc[peak_time] if peak_time in rolling_baseline.index else pre_series.median()

            above_base = pre_series[pre_series > baseline_val * 1.2]
            event_start = above_base.index.min() if not above_base.empty else (peak_time - pd.Timedelta(hours=6))

            # Pre-event sensor window: [event_start - pre_hours, event_start]
            pre_win_start = event_start - pd.Timedelta(hours=pre_hours)
            pre_df = df.loc[pre_win_start:event_start]

            pre_do = (
                round(float(pre_df["dissolved_oxygen"].dropna().median()), 2)
                if "dissolved_oxygen" in df.columns and not pre_df["dissolved_oxygen"].dropna().empty
                else np.nan
            )
            pre_temp = (
                round(float(pre_df["water_temperature"].dropna().median()), 2)
                if "water_temperature" in df.columns and not pre_df["water_temperature"].dropna().empty
                else np.nan
            )

            # Post-event recovery window: [peak_time, peak_time + post_hours]
            post_win_end = peak_time + pd.Timedelta(hours=post_hours)
            post_df = df.loc[peak_time:post_win_end]

            min_do_post = (
                round(float(post_df["dissolved_oxygen"].dropna().min()), 2)
                if "dissolved_oxygen" in df.columns and not post_df["dissolved_oxygen"].dropna().empty
                else np.nan
            )

            do_drop = (
                round(pre_do - min_do_post, 2)
                if not np.isnan(pre_do) and not np.isnan(min_do_post)
                else np.nan
            )

            # Turbidity response during event
            event_full_df = df.loc[event_start:post_win_end]
            turbidity_response = (
                round(float(event_full_df["turbidity"].dropna().max()), 2)
                if "turbidity" in df.columns and not event_full_df["turbidity"].dropna().empty
                else np.nan
            )

            # Approximate recovery period (time for discharge to drop to within 30% above baseline)
            post_q = post_df["discharge"].dropna()
            recovery_target = baseline_val * 1.3
            recovered_series = post_q[post_q <= recovery_target]
            if not recovered_series.empty:
                recovery_time = recovered_series.index.min()
                recovery_hours = round((recovery_time - peak_time).total_seconds() / 3600.0, 1)
            else:
                recovery_hours = np.nan  # Did not recover within post-event observation window

            events.append({
                "station_id": station_id,
                "event_start": event_start.isoformat(),
                "event_peak": peak_time.isoformat(),
                "peak_discharge_cfs": round(peak_discharge, 2),
                "baseline_discharge_cfs": round(float(baseline_val), 2),
                "discharge_spike_ratio": round(peak_discharge / max(float(baseline_val), 0.1), 2),
                "pre_event_do_mg_L": pre_do,
                "min_do_after_event_mg_L": min_do_post,
                "do_drop_mg_L": do_drop,
                "pre_event_temperature_deg_C": pre_temp,
                "turbidity_peak_response": turbidity_response,
                "recovery_period_hours": recovery_hours,
            })

            last_event_time = peak_time

        events_df = pd.DataFrame(events)

        if save_csv:
            out_file = REPORTS_DIR / "candidate_storm_events.csv"
            events_df.to_csv(out_file, index=False)
            logger.info("Saved %d candidate disturbance events to %s", len(events_df), out_file)

        return events_df
