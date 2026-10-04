"""
AquaRehearsal-X - Stage 3 Storm Event Detector & Overlap Resolver
Component: storm_event_detector.py

Identifies hydrologic-meteorological storm disturbance events from the continuous multi-year record:
- Detects disturbance onset (t0) based on discharge surges (>=1.75x rolling median) and rainfall triggers (>1.0 mm/h).
- Extracts pre-storm reference state at t0 (pre-storm water temperature, baseline discharge, baseline DO).
- Calculates cumulative storm rainfall over the defined storm window.
- Computes future 72-hour minimum DO strictly during (t0, t0 + 72h], excluding t0.
- Handles overlapping storm events explicitly: flags clustered storms, prevents evaluation window contamination,
  and extracts independent non-overlapping events for cross-validation and event-level bootstrapping.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
import pandas as pd

from src.utils.logger import logger


class StormEventDetector:
    """
    Detects, characterizes, and resolves overlapping storm disturbance events.
    """

    def __init__(
        self,
        discharge_surge_ratio_threshold: float = 1.75,
        min_peak_discharge_cfs: float = 2500.0,
        min_event_rainfall_mm: float = 5.0,
        storm_window_hours: int = 24,
        evaluation_horizon_hours: int = 72,
        min_separation_hours: int = 48,
    ):
        self.surge_ratio_thresh = discharge_surge_ratio_threshold
        self.min_peak_q = min_peak_discharge_cfs
        self.min_rain_mm = min_event_rainfall_mm
        self.storm_window_hours = storm_window_hours
        self.eval_horizon_hours = evaluation_horizon_hours
        self.min_separation_hours = min_separation_hours

    def detect_events_from_timeseries(self, df_hourly: pd.DataFrame) -> pd.DataFrame:
        """
        Scans continuous hourly time series to detect storm disturbance events.
        
        Requirements:
        - df_hourly must have DatetimeIndex (or 'timestamp' column) and columns:
          'water_temperature', 'dissolved_oxygen', 'discharge', 'rain_mm'.
        """
        df = df_hourly.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp").sort_index()

        # Rolling 7-day baseline discharge (168 hours) strictly backward-looking
        df["q_rolling_median"] = df["discharge"].rolling(168, min_periods=48).median()
        df["surge_ratio"] = df["discharge"] / df["q_rolling_median"].replace(0, np.nan)
        df["rain_24h_rolling"] = df["rain_mm"].rolling(24, min_periods=12).sum()

        events = []
        in_event = False
        event_start = None
        event_peak_time = None
        peak_q = 0.0
        n_rows = len(df)

        i = 168  # Skip burn-in
        while i < n_rows - self.eval_horizon_hours:
            current_time = df.index[i]
            q_val = df["discharge"].iloc[i]
            surge = df["surge_ratio"].iloc[i]
            rain_24 = df["rain_24h_rolling"].iloc[i]

            # Event trigger: surge ratio exceeds threshold AND peak criteria met
            if not in_event:
                if (surge >= self.surge_ratio_thresh or rain_24 >= self.min_rain_mm) and q_val >= 1000.0:
                    in_event = True
                    event_start = current_time
                    event_peak_time = current_time
                    peak_q = q_val
            else:
                if q_val > peak_q:
                    peak_q = q_val
                    event_peak_time = current_time

                # Check event end: discharge drops back towards baseline or min separation reached
                surge_receded = surge < 1.30 or q_val < df["q_rolling_median"].iloc[i] * 1.35
                time_elapsed = (current_time - event_start).total_seconds() / 3600.0

                if (surge_receded and time_elapsed >= 12.0) or time_elapsed >= 72.0:
                    # Finalize candidate event
                    event_duration = max(6.0, time_elapsed)
                    
                    # Pre-storm state strictly at t0 - 1h
                    t0 = event_start
                    pre_t = t0 - pd.Timedelta(hours=1)
                    
                    pre_temp = df.loc[pre_t, "water_temperature"] if pre_t in df.index else np.nan
                    pre_do = df.loc[pre_t, "dissolved_oxygen"] if pre_t in df.index else np.nan
                    pre_q = df.loc[pre_t, "discharge"] if pre_t in df.index else np.nan

                    # Squeeze if duplicate timestamp
                    if isinstance(pre_temp, pd.Series):
                        pre_temp = float(pre_temp.iloc[0])
                    if isinstance(pre_do, pd.Series):
                        pre_do = float(pre_do.iloc[0])
                    if isinstance(pre_q, pd.Series):
                        pre_q = float(pre_q.iloc[0])

                    # Cumulative storm rainfall over storm window
                    storm_end = t0 + pd.Timedelta(hours=self.storm_window_hours)
                    sub_rain = df.loc[t0:storm_end, "rain_mm"].dropna()
                    cum_rain = float(sub_rain.sum()) if not sub_rain.empty else 0.0

                    # 72-hour future DO strictly during (t0, t0 + 72h]
                    future_start = t0 + pd.Timedelta(hours=1)
                    future_end = t0 + pd.Timedelta(hours=self.eval_horizon_hours)
                    sub_future = df.loc[future_start:future_end, "dissolved_oxygen"].dropna()
                    
                    if len(sub_future) >= 48:
                        min_future_do = float(sub_future.min())
                        t_nadir = sub_future.idxmin()
                        lag_to_nadir = (t_nadir - t0).total_seconds() / 3600.0
                    else:
                        min_future_do = np.nan
                        lag_to_nadir = np.nan

                    if peak_q >= self.min_peak_q or cum_rain >= self.min_rain_mm:
                        events.append({
                            "event_id": len(events) + 1,
                            "forecast_issue_time": t0.isoformat(),
                            "event_peak_time": event_peak_time.isoformat(),
                            "duration_hours": round(event_duration, 1),
                            "pre_storm_water_temp_c": round(float(pre_temp), 2) if not np.isnan(pre_temp) else np.nan,
                            "pre_storm_do_mg_L": round(float(pre_do), 2) if not np.isnan(pre_do) else np.nan,
                            "pre_storm_discharge_cfs": round(float(pre_q), 1) if not np.isnan(pre_q) else np.nan,
                            "cumulative_storm_rain_mm": round(cum_rain, 2),
                            "peak_discharge_cfs": round(float(peak_q), 1),
                            "surge_ratio": round(float(peak_q / max(100.0, pre_q)), 2) if not np.isnan(pre_q) else np.nan,
                            "future_min_do_72h": round(min_future_do, 2) if not np.isnan(min_future_do) else np.nan,
                            "observed_time_to_trough_hours": round(lag_to_nadir, 1) if not np.isnan(lag_to_nadir) else np.nan,
                        })

                    # Reset and advance by separation buffer
                    in_event = False
                    i += int(self.min_separation_hours)
                    continue

            i += 1

        df_events = pd.DataFrame(events)
        df_events = self.flag_and_resolve_overlaps(df_events)
        logger.info("Detected %d total storm disturbance events (%d non-overlapping).", len(df_events), df_events["is_non_overlapping"].sum())
        return df_events

    def flag_and_resolve_overlaps(self, df_events: pd.DataFrame) -> pd.DataFrame:
        """
        Flags overlapping 72-hour evaluation windows and marks independent non-overlapping events.
        """
        if df_events.empty:
            df_events["has_72h_window_overlap"] = []
            df_events["is_non_overlapping"] = []
            df_events["cluster_id"] = []
            return df_events

        df = df_events.copy()
        time_col = "forecast_issue_time" if "forecast_issue_time" in df.columns else ("event_start" if "event_start" in df.columns else "start_time")
        df["t_start"] = pd.to_datetime(df[time_col], utc=True)
        df = df.sort_values("t_start").reset_index(drop=True)

        overlaps = []
        is_clean = []
        cluster_ids = []
        current_cluster = 1
        last_clean_end = pd.Timestamp.min.tz_localize("UTC")

        for idx, row in df.iterrows():
            t_curr = row["t_start"]
            t_window_end = t_curr + pd.Timedelta(hours=self.eval_horizon_hours)

            # Check overlap with previous event's evaluation window
            if idx > 0:
                prev_window_end = df.loc[idx - 1, "t_start"] + pd.Timedelta(hours=self.eval_horizon_hours)
                has_overlap = t_curr < prev_window_end
            else:
                has_overlap = False

            if has_overlap:
                overlaps.append(True)
            else:
                overlaps.append(False)
                current_cluster += 1

            cluster_ids.append(current_cluster)

            # Non-overlapping independent event selection: separated by >= 72h
            if t_curr >= last_clean_end:
                is_clean.append(True)
                last_clean_end = t_window_end
            else:
                is_clean.append(False)

        df["has_72h_window_overlap"] = overlaps
        df["is_non_overlapping"] = is_clean
        df["cluster_id"] = cluster_ids
        df = df.drop(columns=["t_start"])
        return df
