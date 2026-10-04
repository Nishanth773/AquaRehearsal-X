"""
AquaRehearsal-X - Historical Event Stress-Testing & STE Evaluator
Stage 3: Event-by-Event Backtesting Across 58 Multi-Year Storm Disturbances

Evaluates the Storm Tolerance Envelope against the complete historical catalog of 58 physical
storm disturbance events (2023-2026) recorded at USGS 01474500 (Schuylkill River at Philadelphia).

Computes:
- Predicted vs observed minimum DO
- Threshold crossing probabilities (P(DO < 5.0), P(DO < 4.0), P(DO < 2.0))
- Operational warning levels (NORMAL, ADVISORY, WARNING, EMERGENCY)
- Action window accuracy (predicted vs observed time-to-trough)
- Early-warning contingency metrics: Sensitivity, Specificity, Precision, F1-Score, Brier Score.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
import pandas as pd

from src.config.stage3_settings import (
    STAGE3_DATA_CONFIG,
    STAGE3_REGULATORY_THRESHOLDS,
    STAGE3_REPORTS_DIR,
    PROCESSED_DATA_DIR,
    STAGE2_5_REPORTS_DIR,
)
from src.ste.envelope_engine import StormToleranceEnvelope
from src.ste.probability_engine import BoundaryCrossingProbability, StratifiedUncertaintyCalibrator
from src.ste.action_window import ActionWindowEstimator
from src.utils.logger import logger


class HistoricalSTEEvaluator:
    """
    Backtests the Storm Tolerance Envelope and early warning system
    across the catalog of 58 historical storm disturbance events.
    """

    def __init__(
        self,
        events_path: Optional[Path] = None,
        timeseries_path: Optional[Path] = None,
        reports_dir: Optional[Path] = None,
    ):
        self.events_path = Path(events_path or (STAGE2_5_REPORTS_DIR / STAGE3_DATA_CONFIG["historical_events_file"]))
        self.timeseries_path = Path(timeseries_path or (PROCESSED_DATA_DIR / STAGE3_DATA_CONFIG["extended_data_file"]))
        self.reports_dir = Path(reports_dir or STAGE3_REPORTS_DIR)
        
        self.ste_engine = StormToleranceEnvelope()
        self.prob_engine = BoundaryCrossingProbability()
        self.window_estimator = ActionWindowEstimator()

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Loads events catalog and aligned hourly time series."""
        logger.info("Loading historical events from %s...", self.events_path)
        df_events = pd.read_csv(self.events_path)
        
        logger.info("Loading extended hourly time series from %s...", self.timeseries_path)
        df_ts = pd.read_csv(self.timeseries_path)
        df_ts["timestamp"] = pd.to_datetime(df_ts["timestamp"], utc=True)
        df_ts = df_ts.set_index("timestamp").sort_index()
        
        return df_events, df_ts

    def evaluate_all_events(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Executes comprehensive STE backtesting across all 58 historical storm events."""
        df_events, df_ts = self.load_data()
        
        evaluation_rows = []
        
        for idx, row in df_events.iterrows():
            event_id = row["event_id"]
            t_start = pd.to_datetime(row["event_start"], utc=True)
            t_end = t_start + pd.Timedelta(hours=72)
            
            # Pre-event state (1 hour before storm onset)
            pre_t = t_start - pd.Timedelta(hours=1)
            if pre_t in df_ts.index:
                ambient_temp = float(df_ts.loc[pre_t, "water_temperature"])
                ambient_do = float(df_ts.loc[pre_t, "dissolved_oxygen"])
                ambient_q = float(df_ts.loc[pre_t, "discharge"])
            else:
                # Fallback to event row values if exact pre-timestamp missing
                ambient_temp = 18.0
                ambient_do = float(row.get("pre_event_do_mg_L", 8.0))
                ambient_q = float(row.get("peak_discharge_cfs", 2000.0)) / max(1.0, float(row.get("discharge_increase_ratio", 2.0)))
            
            # Squeeze / handle series if duplicate indices exist
            if isinstance(ambient_temp, pd.Series):
                ambient_temp = float(ambient_temp.iloc[0])
            if isinstance(ambient_do, pd.Series):
                ambient_do = float(ambient_do.iloc[0])
            if isinstance(ambient_q, pd.Series):
                ambient_q = float(ambient_q.iloc[0])

            # Antecedent 72h rainfall
            api_start = t_start - pd.Timedelta(hours=72)
            sub_api = df_ts.loc[api_start:pre_t, "rain_mm"]
            api_72h = float(sub_api.sum()) if not sub_api.empty else float(row.get("rainfall_before_event_24h_mm", 0.0)) * 1.5

            # Storm forcing
            storm_rain = float(row.get("cumulative_rainfall_mm", 0.0))
            surge_ratio = float(row.get("discharge_increase_ratio", 2.0))
            duration_hours = float(row.get("event_duration_hours", 12.0))
            peak_q = float(row.get("peak_discharge_cfs", ambient_q * surge_ratio))

            # Observed future 72h minimum DO and time-to-trough
            sub_future = df_ts.loc[t_start:t_end, "dissolved_oxygen"].dropna()
            if not sub_future.empty:
                observed_min_do = float(sub_future.min())
                t_nadir = sub_future.idxmin()
                observed_lag_hours = float((t_nadir - t_start).total_seconds() / 3600.0)
            else:
                observed_min_do = float(row.get("minimum_future_do_mg_L", ambient_do))
                observed_lag_hours = np.nan

            # 1. Evaluate Storm Tolerance Envelope
            ste_eval = self.ste_engine.evaluate_envelope(
                ambient_temp_c=ambient_temp,
                ambient_do_mg_L=ambient_do,
                ambient_discharge_cfs=ambient_q,
                incoming_rain_mm=storm_rain,
                incoming_discharge_surge_ratio=surge_ratio,
                antecedent_rain_72h_mm=api_72h,
            )
            pred_min_do = ste_eval["expected_minimum_do_mg_L"]

            # 2. Compute Boundary-Crossing Probabilities & Alert Level
            probs = self.prob_engine.compute_crossing_probabilities(
                expected_min_do=pred_min_do,
                ambient_temp_c=ambient_temp,
            )
            interval_low, interval_high = self.prob_engine.compute_prediction_interval(
                expected_min_do=pred_min_do,
                ambient_temp_c=ambient_temp,
            )
            alert_info = self.prob_engine.determine_alert_level(
                expected_min_do=pred_min_do,
                p_acute_4_0=probs["p_crossing_acute_4_0"],
                p_hypoxia_2_0=probs["p_crossing_hypoxia_2_0"],
            )

            # 3. Estimate Action Window
            pred_time_to_trough = self.window_estimator.estimate_time_to_trough(
                storm_duration_hours=duration_hours,
                discharge_surge_ratio=surge_ratio,
                water_temperature_c=ambient_temp,
                storm_rainfall_mm=storm_rain,
            )
            window_info = self.window_estimator.characterize_action_window(pred_time_to_trough)

            # 4. Actual Regulatory Breach Outcomes
            actual_breached_standard_5_0 = bool(observed_min_do < 5.0)
            actual_breached_acute_4_0 = bool(observed_min_do < 4.0)
            predicted_breach_standard = bool(probs["p_crossing_standard_5_0"] >= 0.35 or pred_min_do < 5.0)
            predicted_breach_acute = bool(probs["p_crossing_acute_4_0"] >= 0.35 or pred_min_do < 4.0)

            evaluation_rows.append({
                "event_id": event_id,
                "partition": row.get("partition", "TRAIN"),
                "event_start": row["event_start"],
                "ambient_temp_c": round(ambient_temp, 2),
                "ambient_do_mg_L": round(ambient_do, 2),
                "ambient_discharge_cfs": round(ambient_q, 1),
                "antecedent_rain_72h_mm": round(api_72h, 1),
                "storm_rain_mm": round(storm_rain, 1),
                "peak_discharge_cfs": round(peak_q, 1),
                "surge_ratio": round(surge_ratio, 2),
                "duration_hours": round(duration_hours, 1),
                "observed_min_do_72h": round(observed_min_do, 2),
                "predicted_min_do_72h": round(pred_min_do, 2),
                "pred_error_mg_L": round(pred_min_do - observed_min_do, 2),
                "pred_interval_80_lower": interval_low,
                "pred_interval_80_upper": interval_high,
                "p_crossing_standard_5_0": probs["p_crossing_standard_5_0"],
                "p_crossing_acute_4_0": probs["p_crossing_acute_4_0"],
                "p_crossing_hypoxia_2_0": probs["p_crossing_hypoxia_2_0"],
                "alert_level": alert_info["key"],
                "alert_label": alert_info["label"],
                "r_crit_standard_5_0_mm": ste_eval["critical_rainfall_standard_5_0_mm"],
                "r_crit_acute_4_0_mm": ste_eval["critical_rainfall_acute_4_0_mm"],
                "remaining_capacity_pct": ste_eval["remaining_assimilative_capacity_pct"],
                "predicted_time_to_trough_h": pred_time_to_trough,
                "observed_time_to_trough_h": round(observed_lag_hours, 1) if not np.isnan(observed_lag_hours) else np.nan,
                "actionable_window_h": window_info["actionable_window_hours"],
                "action_urgency": window_info["urgency_tier"],
                "actual_breached_standard_5_0": actual_breached_standard_5_0,
                "actual_breached_acute_4_0": actual_breached_acute_4_0,
                "predicted_breach_standard": predicted_breach_standard,
                "predicted_breach_acute": predicted_breach_acute,
            })

        df_results = pd.DataFrame(evaluation_rows)
        
        # Calculate contingency statistics for Standard Protection (5.0 mg/L)
        y_act_std = df_results["actual_breached_standard_5_0"].values
        y_pred_std = df_results["predicted_breach_standard"].values
        
        tp = int(np.sum((y_pred_std == True) & (y_act_std == True)))
        fp = int(np.sum((y_pred_std == True) & (y_act_std == False)))
        fn = int(np.sum((y_pred_std == False) & (y_act_std == True)))
        tn = int(np.sum((y_pred_std == False) & (y_act_std == False)))
        
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fn == 0 else 0.0)
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = (2 * precision * sensitivity) / (precision + sensitivity) if (precision + sensitivity) > 0 else 0.0

        # Calculate contingency statistics for Significant DO Depletion Stress (Depletion >= 1.0 mg/L or DO <= 6.5 mg/L)
        actual_stress = ((df_results["observed_min_do_72h"] <= 6.5) | ((df_results["ambient_do_mg_L"] - df_results["observed_min_do_72h"]) >= 1.0)).values
        predicted_stress = df_results["alert_level"].isin(["ADVISORY", "WARNING", "EMERGENCY"]).values
        tp_stress = int(np.sum((predicted_stress == True) & (actual_stress == True)))
        fp_stress = int(np.sum((predicted_stress == True) & (actual_stress == False)))
        fn_stress = int(np.sum((predicted_stress == False) & (actual_stress == True)))
        tn_stress = int(np.sum((predicted_stress == False) & (actual_stress == False)))

        sens_stress = tp_stress / (tp_stress + fn_stress) if (tp_stress + fn_stress) > 0 else 0.0
        spec_stress = tn_stress / (tn_stress + fp_stress) if (tn_stress + fp_stress) > 0 else 0.0
        prec_stress = tp_stress / (tp_stress + fp_stress) if (tp_stress + fp_stress) > 0 else 0.0
        f1_stress = (2 * prec_stress * sens_stress) / (prec_stress + sens_stress) if (prec_stress + sens_stress) > 0 else 0.0
        
        # Brier Score for P(DO < 5.0)
        p_std = df_results["p_crossing_standard_5_0"].values
        brier_std = float(np.mean((p_std - y_act_std.astype(float)) ** 2))
        
        # Time-to-trough MAE for events with valid observed lags
        valid_lags = df_results.dropna(subset=["observed_time_to_trough_h"])
        lag_mae = float(np.mean(np.abs(valid_lags["predicted_time_to_trough_h"] - valid_lags["observed_time_to_trough_h"])))

        summary_metrics = {
            "total_historical_events": len(df_results),
            "events_breaching_5_0_standard": int(np.sum(y_act_std)),
            "events_breaching_4_0_acute": int(np.sum(df_results["actual_breached_acute_4_0"])),
            "true_positives_std": tp,
            "false_positives_std": fp,
            "false_negatives_std": fn,
            "true_negatives_std": tn,
            "sensitivity_recall": round(sensitivity, 3),
            "specificity": round(specificity, 3),
            "precision": round(precision, 3),
            "f1_score": round(f1, 3),
            "events_with_deoxygenation_stress": int(np.sum(actual_stress)),
            "stress_tp": tp_stress,
            "stress_fp": fp_stress,
            "stress_fn": fn_stress,
            "stress_tn": tn_stress,
            "stress_sensitivity": round(sens_stress, 3),
            "stress_specificity": round(spec_stress, 3),
            "stress_precision": round(prec_stress, 3),
            "stress_f1_score": round(f1_stress, 3),
            "brier_score_std_5_0": round(brier_std, 4),
            "time_to_trough_mae_hours": round(lag_mae, 2),
            "alert_counts": df_results["alert_level"].value_counts().to_dict(),
        }

        # Persist results
        csv_path = self.reports_dir / "historical_ste_evaluations.csv"
        df_results.to_csv(csv_path, index=False)
        logger.info("Saved historical STE evaluations to %s", csv_path)

        summary_df = pd.DataFrame([summary_metrics])
        summary_df.to_csv(self.reports_dir / "ste_contingency_summary.csv", index=False)

        return df_results, summary_metrics
