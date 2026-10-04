"""
AquaRehearsal-X - Storm-Event Backtester
72-Hour Dissolved Oxygen Forecasting Engine

Simulates historical event-response forecasting:
"What would AquaRehearsal-X have predicted if this storm were approaching at that time?"

Integrity Mandate:
- Uses ONLY information available at or immediately before event onset (t <= event_start).
- Evaluates predicted minimum DO against actual observed minimum DO over the subsequent 72 hours.
- Segregates events by partition (TRAIN, VAL, TEST) to prevent test-set tuning.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import numpy as np
import pandas as pd

from src.utils.logger import logger


class StormEventBacktester:
    """Executes pre-event 72-hour minimum DO forecasting backtests on candidate storm events."""

    def __init__(
        self,
        candidate_events_df: pd.DataFrame,
        split_boundaries: Dict[str, str],
    ):
        self.events_df = candidate_events_df.copy()
        self.split_boundaries = split_boundaries
        if "event_start" in self.events_df.columns:
            self.events_df["event_start"] = pd.to_datetime(self.events_df["event_start"], utc=True)

    def run_backtests(
        self,
        features_df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        ml_model: Any,
        baseline_a: Any,
        baseline_b: Any,
        quantile_model: Optional[Any] = None,
        conformal_calibrator: Optional[Any] = None,
    ) -> pd.DataFrame:
        """
        Runs backtesting across all candidate storm events.

        Args:
            features_df: Full DataFrame containing features and target, indexed by UTC DatetimeIndex.
            feature_cols: List of feature names.
            target_col: Name of target column (target_min_do_72h).
            ml_model: Trained DissolvedOxygenForecaster.
            baseline_a: PersistenceBaseline.
            baseline_b: LinearSeasonalBaseline.
            quantile_model: QuantileForecaster (optional).
            conformal_calibrator: SplitConformalCalibrator (optional).

        Returns:
            DataFrame containing backtest results for each event.
        """
        results = []
        train_end = pd.to_datetime(self.split_boundaries.get("train_end", "2026-07-20 00:00:00+00:00"), utc=True)
        val_end = pd.to_datetime(self.split_boundaries.get("val_end", "2026-08-25 00:00:00+00:00"), utc=True)
        test_end = pd.to_datetime(self.split_boundaries.get("test_end", "2026-09-25 15:00:00+00:00"), utc=True)

        for idx, row in self.events_df.iterrows():
            event_start = row["event_start"]

            # Determine partition
            if event_start < train_end:
                partition = "TRAIN"
            elif event_start < val_end:
                partition = "VAL"
            elif event_start <= test_end:
                partition = "TEST"
            else:
                partition = "POST_TEST"

            # Find latest available hourly observation at or before event_start
            valid_indices = features_df.index[features_df.index <= event_start]
            if len(valid_indices) == 0:
                logger.warning("No pre-event data found for event at %s", event_start)
                continue

            pred_time = valid_indices[-1]
            sample_features = features_df.loc[[pred_time], feature_cols]
            actual_min_do = features_df.loc[pred_time, target_col]

            if pd.isna(actual_min_do):
                logger.warning("Incomplete future 72h window for event at %s. Skipping.", event_start)
                continue

            # Model predictions using ONLY pre-event features
            pred_ml = float(ml_model.predict(sample_features)[0])
            pred_base_a = float(baseline_a.predict(sample_features)[0])
            pred_base_b = float(baseline_b.predict(sample_features)[0])

            # Quantiles if available
            q10, q50, q90 = np.nan, np.nan, np.nan
            if quantile_model is not None and quantile_model.models:
                q_preds = quantile_model.predict(sample_features)
                q10 = float(q_preds["q_0.10"].iloc[0]) if "q_0.10" in q_preds else np.nan
                q50 = float(q_preds["q_0.50"].iloc[0]) if "q_0.50" in q_preds else np.nan
                q90 = float(q_preds["q_0.90"].iloc[0]) if "q_0.90" in q_preds else np.nan

            # Conformal interval if available
            conf_lower, conf_upper = np.nan, np.nan
            if conformal_calibrator is not None and conformal_calibrator.conformal_quantile_margin is not None:
                c_low, c_up = conformal_calibrator.predict_interval(np.array([pred_ml]))
                conf_lower = float(c_low[0])
                conf_upper = float(c_up[0])

            # Errors
            err_ml = pred_ml - actual_min_do
            abs_err_ml = abs(err_ml)
            err_base_a = pred_base_a - actual_min_do
            abs_err_base_a = abs(err_base_a)
            err_base_b = pred_base_b - actual_min_do
            abs_err_base_b = abs(err_base_b)

            results.append({
                "event_id": idx + 1,
                "partition": partition,
                "event_start": event_start.isoformat(),
                "prediction_timestamp": pred_time.isoformat(),
                "peak_discharge_cfs": row.get("peak_discharge_cfs", np.nan),
                "actual_min_do_72h": round(actual_min_do, 2),
                "pred_ml": round(pred_ml, 2),
                "error_ml": round(err_ml, 2),
                "abs_error_ml": round(abs_err_ml, 2),
                "pred_base_a": round(pred_base_a, 2),
                "abs_error_base_a": round(abs_err_base_a, 2),
                "pred_base_b": round(pred_base_b, 2),
                "abs_error_base_b": round(abs_err_base_b, 2),
                "quantile_10": round(q10, 2) if np.isfinite(q10) else None,
                "quantile_50": round(q50, 2) if np.isfinite(q50) else None,
                "quantile_90": round(q90, 2) if np.isfinite(q90) else None,
                "in_quantile_interval": bool(q10 <= actual_min_do <= q90) if np.isfinite(q10) and np.isfinite(q90) else None,
                "conformal_lower": round(conf_lower, 2) if np.isfinite(conf_lower) else None,
                "conformal_upper": round(conf_upper, 2) if np.isfinite(conf_upper) else None,
                "in_conformal_interval": bool(conf_lower <= actual_min_do <= conf_upper) if np.isfinite(conf_lower) and np.isfinite(conf_upper) else None,
            })

        df_res = pd.DataFrame(results)
        logger.info(
            "Completed storm-event backtesting across %d events (%d train, %d val, %d test).",
            len(df_res),
            len(df_res[df_res["partition"] == "TRAIN"]),
            len(df_res[df_res["partition"] == "VAL"]),
            len(df_res[df_res["partition"] == "TEST"]),
        )
        return df_res
