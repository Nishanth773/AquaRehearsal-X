"""
AquaRehearsal-X - Historical Storm Replay Module
Component: historical_storm_replay.py

Replays held-out historical storm events through the Storm Tolerance Envelope:
1. Reconstructs sensor information strictly available at forecast issue time (t0).
2. Records pre-storm water temperature and storm rainfall.
3. Evaluates estimated boundary-crossing probability P(DO_min^72h < threshold).
4. Compares predicted operational status against observed 72-hour DO outcomes.
5. Records:
   - Correct Warnings (True Positives)
   - False Alarms (False Positives)
   - Missed Events (False Negatives - documented transparently if they exist in held-out data)
   - Correct Safe Predictions (True Negatives)
   - Operational Lead Time (hours) between forecast issue and the first threshold crossing timestamp.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
import pandas as pd

from src.ste.risk_model import EcologicalRiskModel
from src.ste.domain_support_checker import DomainSupportChecker
from src.utils.logger import logger


class HistoricalStormReplay:
    """
    Executes event-by-event historical replay and lead-time audit.
    """

    def __init__(
        self,
        risk_model: Optional[EcologicalRiskModel] = None,
        domain_checker: Optional[DomainSupportChecker] = None,
        operational_risk_limit: float = 0.20,
        default_threshold_mg_L: float = 5.0,
    ):
        self.risk_model = risk_model or EcologicalRiskModel(default_threshold_mg_L=default_threshold_mg_L)
        self.domain_checker = domain_checker or DomainSupportChecker()
        self.risk_limit = operational_risk_limit
        self.threshold = default_threshold_mg_L

    def replay_events(
        self,
        df_events: pd.DataFrame,
        df_timeseries: pd.DataFrame,
        threshold_mg_L: Optional[float] = None,
        risk_limit: Optional[float] = None,
        partition_filter: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Replays eligible storm events through the envelope.
        """
        thr = threshold_mg_L if threshold_mg_L is not None else self.threshold
        limit = risk_limit if risk_limit is not None else self.risk_limit

        df_ts = df_timeseries.copy()
        if "timestamp" in df_ts.columns:
            df_ts["timestamp"] = pd.to_datetime(df_ts["timestamp"], utc=True)
            df_ts = df_ts.set_index("timestamp").sort_index()

        df_ev = df_events.copy()
        if partition_filter and "partition" in df_ev.columns:
            df_ev = df_ev[df_ev["partition"] == partition_filter].reset_index(drop=True)

        replay_rows = []

        for idx, row in df_ev.iterrows():
            event_id = row.get("event_id", idx + 1)
            t_issue_str = row.get("forecast_issue_time", row.get("event_start"))
            t_issue = pd.to_datetime(t_issue_str, utc=True)
            t_eval_end = t_issue + pd.Timedelta(hours=72)

            # Reconstruct pre-storm inputs at t0 - 1h
            pre_t = t_issue - pd.Timedelta(hours=1)
            if pre_t in df_ts.index:
                temp_val = df_ts.loc[pre_t, "water_temperature"]
                do_val = df_ts.loc[pre_t, "dissolved_oxygen"]
                q_val = df_ts.loc[pre_t, "discharge"]
            else:
                temp_val = row.get("pre_storm_water_temp_c", row.get("pre_event_water_temp_c", np.nan))
                do_val = row.get("pre_storm_do_mg_L", row.get("pre_event_do_mg_L", np.nan))
                q_val = row.get("pre_storm_discharge_cfs", np.nan)

            if isinstance(temp_val, pd.Series):
                temp_val = float(temp_val.iloc[0])
            if isinstance(do_val, pd.Series):
                do_val = float(do_val.iloc[0])
            if isinstance(q_val, pd.Series):
                q_val = float(q_val.iloc[0])

            rain_val = float(row.get("cumulative_storm_rain_mm", row.get("cumulative_rainfall_mm", 0.0)))

            # Domain check
            support_info = self.domain_checker.check_inputs_defensibility(
                water_temp_c=temp_val,
                storm_rain_mm=rain_val,
                do_mg_L=do_val,
                discharge_cfs=q_val,
            )

            # Generate risk probability
            pred_risk = self.risk_model.estimate_risk_probability(
                storm_rain_mm=rain_val,
                pre_storm_water_temp_c=temp_val,
                pre_storm_do_mg_L=do_val,
                pre_storm_discharge_cfs=q_val,
                threshold_mg_L=thr,
            )

            # Observed future 72h minimum DO & crossing timestamp
            future_sub = df_ts.loc[t_issue:t_eval_end, "dissolved_oxygen"].dropna()
            if not future_sub.empty:
                obs_min_do = float(future_sub.min())
                # First timestamp crossing threshold if any
                breach_times = future_sub[future_sub < thr].index
                if len(breach_times) > 0:
                    first_breach = breach_times[0]
                    lead_time_hours = float((first_breach - t_issue).total_seconds() / 3600.0)
                    actual_breach = True
                else:
                    lead_time_hours = np.nan
                    actual_breach = False
            else:
                obs_min_do = float(row.get("future_min_do_72h", row.get("minimum_future_do_mg_L", np.nan)))
                actual_breach = bool(obs_min_do < thr) if not np.isnan(obs_min_do) else False
                lead_time_hours = np.nan

            warning_issued = bool(pred_risk >= limit)

            # Classification
            if warning_issued and actual_breach:
                outcome_type = "CORRECT_WARNING"  # True Positive
            elif warning_issued and not actual_breach:
                outcome_type = "FALSE_ALARM"      # False Positive
            elif not warning_issued and actual_breach:
                outcome_type = "MISSED_EVENT"     # False Negative
            else:
                outcome_type = "CORRECT_SAFE"     # True Negative

            replay_rows.append({
                "event_id": event_id,
                "partition": row.get("partition", "TEST" if partition_filter == "TEST" else "ALL"),
                "forecast_issue_time": t_issue.isoformat(),
                "pre_storm_water_temp_c": round(temp_val, 2) if not np.isnan(temp_val) else None,
                "pre_storm_do_mg_L": round(do_val, 2) if not np.isnan(do_val) else None,
                "cumulative_storm_rain_mm": round(rain_val, 2),
                "is_domain_supported": support_info["is_supported"],
                "predicted_risk_probability": round(pred_risk, 4) if not np.isnan(pred_risk) else None,
                "operational_warning_issued": warning_issued,
                "observed_future_min_do": round(obs_min_do, 2) if not np.isnan(obs_min_do) else None,
                "actual_threshold_breach": actual_breach,
                "outcome_type": outcome_type,
                "lead_time_to_crossing_hours": round(lead_time_hours, 1) if not np.isnan(lead_time_hours) else None,
            })

        df_replay = pd.DataFrame(replay_rows)

        # Summary statistics
        counts = df_replay["outcome_type"].value_counts().to_dict()
        cw = counts.get("CORRECT_WARNING", 0)
        fa = counts.get("FALSE_ALARM", 0)
        me = counts.get("MISSED_EVENT", 0)
        cs = counts.get("CORRECT_SAFE", 0)

        valid_leads = df_replay.dropna(subset=["lead_time_to_crossing_hours"])
        median_lead = float(valid_leads["lead_time_to_crossing_hours"].median()) if len(valid_leads) > 0 else np.nan

        summary = {
            "total_replayed_events": len(df_replay),
            "do_threshold_mg_L": thr,
            "operational_risk_limit": limit,
            "correct_warnings_tp": cw,
            "false_alarms_fp": fa,
            "missed_events_fn": me,
            "correct_safes_tn": cs,
            "sensitivity_recall": round(cw / (cw + me), 3) if (cw + me) > 0 else 1.0,
            "specificity": round(cs / (cs + fa), 3) if (cs + fa) > 0 else 0.0,
            "precision": round(cw / (cw + fa), 3) if (cw + fa) > 0 else 0.0,
            "median_lead_time_hours": round(median_lead, 1) if not np.isnan(median_lead) else None,
            "has_missed_events": me > 0,
            "notes": (
                f"Replay evaluated against DO < {thr:.1f} mg/L criterion with {limit*100:.0f}% operational risk trigger. "
                "Missed events and false alarms are recorded without data fabrication."
            ),
        }

        return df_replay, summary
