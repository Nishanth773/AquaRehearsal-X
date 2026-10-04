"""
AquaRehearsal-X - Stage 2.5 Historical Storm/Disturbance Event Detection
Historical Depth + Real Precipitation Upgrade

Identifies candidate storm/disturbance events across the 3.75-year extended record (2023-2026)
and enriches each event with real precipitation metrics:
- 24h antecedent rainfall before event
- Peak hourly rainfall
- Cumulative storm rainfall
- Peak discharge and surge ratio
- Pre-event DO and future 72h minimum DO
- DO depletion and recovery duration

Terminology Mandate:
- Events are designated strictly as 'storm/disturbance events' based on physical discharge surges
  and rainfall pulses, without assuming arbitrary ecological collapse.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

from src.config.stage2_5_settings import (
    STAGE2_5_DATA_CONFIG,
    STAGE2_5_SPLIT_CONFIG,
    STAGE2_5_REPORTS_DIR,
    PROCESSED_DATA_DIR,
)
from src.analysis.disturbance import DisturbanceDetector
from src.config.settings import DISTURBANCE_CONFIG
from src.utils.logger import logger


class HistoricalStormEnricher:
    """Detects multi-year disturbance events and enriches them with real precipitation telemetry."""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = Path(data_path or PROCESSED_DATA_DIR / STAGE2_5_DATA_CONFIG["extended_data_file"])
        self.split_config = STAGE2_5_SPLIT_CONFIG
        self.reports_dir = STAGE2_5_REPORTS_DIR

    def detect_and_enrich_events(self) -> pd.DataFrame:
        """Runs disturbance detection on extended data and merges precipitation characteristics."""
        logger.info("Detecting and enriching historical storm/disturbance events across 2023-2026...")

        df = pd.read_csv(self.data_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()

        # Run base disturbance detector
        detector = DisturbanceDetector(config=DISTURBANCE_CONFIG)
        base_events = detector.detect_candidate_events(df, station_id=STAGE2_5_DATA_CONFIG["station_id"])

        if base_events.empty:
            logger.warning("No disturbance events detected.")
            return pd.DataFrame()

        base_events["event_start"] = pd.to_datetime(base_events["event_start"], utc=True)
        base_events["event_peak"] = pd.to_datetime(base_events["event_peak"], utc=True)

        train_end = pd.to_datetime(self.split_config["train_end"], utc=True)
        val_end = pd.to_datetime(self.split_config["val_end"], utc=True)
        test_end = pd.to_datetime(self.split_config["test_end"], utc=True)

        enriched_records = []
        precip_series = df["rain_mm"] if "rain_mm" in df.columns else (df["precipitation_mm"] if "precipitation_mm" in df.columns else pd.Series(index=df.index, dtype=float))

        for idx, row in base_events.iterrows():
            e_start = row["event_start"]
            e_peak = row["event_peak"]

            # Chronological partition
            if e_start < train_end:
                partition = "TRAIN"
            elif e_start < val_end:
                partition = "VAL"
            elif e_start <= test_end:
                partition = "TEST"
            else:
                partition = "POST_TEST"

            # 1. 24h rainfall before event onset
            pre_rain_start = e_start - pd.Timedelta(hours=24)
            pre_rain_slice = precip_series.loc[(precip_series.index >= pre_rain_start) & (precip_series.index <= e_start)]
            rainfall_before_24h = float(pre_rain_slice.sum()) if not pre_rain_slice.empty else np.nan

            # 2. Storm window rainfall (from 24h pre-event to peak + 24h)
            storm_rain_end = e_peak + pd.Timedelta(hours=24)
            storm_rain_slice = precip_series.loc[(precip_series.index >= pre_rain_start) & (precip_series.index <= storm_rain_end)]
            peak_rain = float(storm_rain_slice.max()) if not storm_rain_slice.empty else np.nan
            cum_rain = float(storm_rain_slice.sum()) if not storm_rain_slice.empty else np.nan

            # 3. Post-event 72-hour future minimum DO
            post_do_slice = df.loc[(df.index > e_start) & (df.index <= e_start + pd.Timedelta(hours=72)), "dissolved_oxygen"]
            min_future_do = float(post_do_slice.min()) if not post_do_slice.empty and post_do_slice.notna().sum() >= 58 else np.nan

            pre_do = row.get("pre_event_do_mg_L")
            do_depletion = round(pre_do - min_future_do, 2) if (pre_do is not None and np.isfinite(min_future_do)) else np.nan

            # 4. Turbidity peak response
            turb_slice = df.loc[(df.index >= e_start) & (df.index <= e_peak + pd.Timedelta(hours=48)), "turbidity"] if "turbidity" in df.columns else pd.Series(dtype=float)
            turb_peak = float(turb_slice.max()) if (not turb_slice.empty and turb_slice.notna().any()) else np.nan

            # Event duration (hours from event_start to event_peak + 24h)
            event_dur = round((e_peak - e_start).total_seconds() / 3600.0, 1)

            enriched_records.append({
                "event_id": idx + 1,
                "partition": partition,
                "event_start": e_start.isoformat(),
                "event_peak": e_peak.isoformat(),
                "rainfall_before_event_24h_mm": round(rainfall_before_24h, 2) if np.isfinite(rainfall_before_24h) else np.nan,
                "peak_rainfall_mm": round(peak_rain, 2) if np.isfinite(peak_rain) else np.nan,
                "cumulative_rainfall_mm": round(cum_rain, 2) if np.isfinite(cum_rain) else np.nan,
                "event_duration_hours": event_dur,
                "peak_discharge_cfs": row.get("peak_discharge_cfs"),
                "discharge_increase_ratio": row.get("discharge_spike_ratio"),
                "turbidity_peak_response": round(turb_peak, 2) if np.isfinite(turb_peak) else np.nan,
                "pre_event_do_mg_L": round(pre_do, 2) if pre_do is not None else np.nan,
                "minimum_future_do_mg_L": round(min_future_do, 2) if np.isfinite(min_future_do) else np.nan,
                "do_depletion_mg_L": do_depletion,
                "recovery_duration_hours": row.get("recovery_period_hours"),
            })

        df_enriched = pd.DataFrame(enriched_records)
        out_csv = self.reports_dir / "historical_storm_events.csv"
        df_enriched.to_csv(out_csv, index=False)
        logger.info(
            "Saved %d enriched historical storm/disturbance events to %s (%d train, %d val, %d test)",
            len(df_enriched),
            out_csv,
            len(df_enriched[df_enriched["partition"] == "TRAIN"]),
            len(df_enriched[df_enriched["partition"] == "VAL"]),
            len(df_enriched[df_enriched["partition"] == "TEST"]),
        )
        return df_enriched


if __name__ == "__main__":
    enricher = HistoricalStormEnricher()
    df_ev = enricher.detect_and_enrich_events()
    print(df_ev.head(5).to_string())
