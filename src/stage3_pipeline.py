"""
AquaRehearsal-X - Stage 3 Master Pipeline Orchestrator
Probabilistic Ecological Safe-Boundary Engine (Storm Tolerance Envelope)

Executes the modular Stage 3 scientific workflow:
1. Event Identification & Overlapping Window Resolution (storm_event_detector)
2. Domain Support & Refusal Enforcer (domain_support_checker)
3. Probabilistic Ecological Risk Modeling (risk_model)
4. Calibration, Brier Score & Discrimination Evaluation (risk_calibration)
5. 2D Rainfall-vs-Temperature Envelope Generation (envelope_generator)
6. Event-Level Bootstrap Boundary Uncertainty (boundary_uncertainty)
7. Historical Storm Replay & Lead-Time Audit (historical_storm_replay)
8. Visualizations & Interactive Platform Deployment (envelope_visualization + ste_plotting)
9. Metadata & Audit Trail Persistence
"""

import sys
from pathlib import Path
import json

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.config.stage3_settings import (
    STAGE3_REPORTS_DIR,
    STAGE3_MODELS_DIR,
    STAGE3_PLOTS_DIR,
    STAGE3_DATA_CONFIG,
    STAGE2_5_REPORTS_DIR,
    PROCESSED_DATA_DIR,
)
from src.ste.storm_event_detector import StormEventDetector
from src.ste.domain_support_checker import DomainSupportChecker
from src.ste.risk_model import EcologicalRiskModel
from src.ste.risk_calibration import RiskCalibrator
from src.ste.envelope_generator import StormToleranceEnvelopeGenerator
from src.ste.boundary_uncertainty import BoundaryUncertaintyEstimator
from src.ste.historical_storm_replay import HistoricalStormReplay
from src.ste.envelope_visualization import EnvelopeVisualizer
from src.ste.probability_engine import StratifiedUncertaintyCalibrator
from src.ste.event_evaluator import HistoricalSTEEvaluator
from src.ste.ste_plotting import Stage3Plotter
from src.utils.logger import logger


class Stage3Pipeline:
    """Master reproducible orchestrator for Stage 3."""

    def __init__(
        self,
        default_threshold_mg_L: float = 5.0,
        operational_risk_limit: float = 0.20,
    ):
        self.threshold = default_threshold_mg_L
        self.risk_limit = operational_risk_limit
        self.reports_dir = STAGE3_REPORTS_DIR
        self.models_dir = STAGE3_MODELS_DIR
        self.plots_dir = STAGE3_PLOTS_DIR

        self.timeseries_path = PROCESSED_DATA_DIR / STAGE3_DATA_CONFIG["extended_data_file"]
        self.events_path = STAGE2_5_REPORTS_DIR / STAGE3_DATA_CONFIG["historical_events_file"]

    def run(self) -> Dict[str, Any]:
        """Runs the complete modular Stage 3 pipeline."""
        print("\n" + "=" * 80)
        print("AQUAREHEARSAL-X — STAGE 3: STORM TOLERANCE ENVELOPE (STE) MASTER PIPELINE")
        print("Probabilistic Ecological Safe-Boundary Engine")
        print("=" * 80 + "\n")

        # -------------------------------------------------------------
        # 1. LOAD DATA & STORM EVENTS
        # -------------------------------------------------------------
        logger.info("Loading extended multi-year dataset from %s...", self.timeseries_path)
        df_ts = pd.read_csv(self.timeseries_path)
        df_ts["timestamp"] = pd.to_datetime(df_ts["timestamp"], utc=True)
        df_ts = df_ts.set_index("timestamp").sort_index()

        logger.info("Loading historical storm events from %s...", self.events_path)
        df_events = pd.read_csv(self.events_path)

        # Standardize column names and enrich pre-storm attributes from timeseries
        if "cumulative_storm_rain_mm" not in df_events.columns and "cumulative_rainfall_mm" in df_events.columns:
            df_events["cumulative_storm_rain_mm"] = df_events["cumulative_rainfall_mm"]
        if "forecast_issue_time" not in df_events.columns and "event_start" in df_events.columns:
            df_events["forecast_issue_time"] = df_events["event_start"]
        if "future_min_do_72h" not in df_events.columns and "minimum_future_do_mg_L" in df_events.columns:
            df_events["future_min_do_72h"] = df_events["minimum_future_do_mg_L"]

        if "pre_storm_water_temp_c" not in df_events.columns:
            pre_temps = []
            for _, row in df_events.iterrows():
                t0_str = row.get("forecast_issue_time", row.get("event_start"))
                t0 = pd.to_datetime(t0_str, utc=True)
                pre_t = t0 - pd.Timedelta(hours=1)
                temp = df_ts.loc[pre_t, "water_temperature"] if pre_t in df_ts.index else np.nan
                if isinstance(temp, pd.Series):
                    temp = float(temp.iloc[0])
                pre_temps.append(round(float(temp), 2) if not np.isnan(temp) else 18.0)
            df_events["pre_storm_water_temp_c"] = pre_temps

        # -------------------------------------------------------------
        # 2. RESOLVE OVERLAPPING EVENTS (storm_event_detector)
        # -------------------------------------------------------------
        detector = StormEventDetector()
        df_events_flagged = detector.flag_and_resolve_overlaps(df_events)
        n_overlapping = int(df_events_flagged["has_72h_window_overlap"].sum())
        n_clean = int(df_events_flagged["is_non_overlapping"].sum())
        logger.info("Events overlap audit: %d events share overlapping 72h windows; %d independent event units.", n_overlapping, n_clean)

        # -------------------------------------------------------------
        # 3. DOMAIN SUPPORT CHECKER (domain_support_checker)
        # -------------------------------------------------------------
        checker = DomainSupportChecker()
        checker.fit_from_historical_events(df_events)

        # -------------------------------------------------------------
        # 4. THERMALLY STRATIFIED UNCERTAINTY & RISK MODEL (risk_model)
        # -------------------------------------------------------------
        calibrator = StratifiedUncertaintyCalibrator(target_coverage=0.80)
        test_pred_path = STAGE2_5_REPORTS_DIR / "stage2_5_test_predictions.csv"
        if test_pred_path.exists():
            df_preds = pd.read_csv(test_pred_path)
            df_preds["timestamp"] = pd.to_datetime(df_preds["timestamp"], utc=True)
            df_preds = df_preds.set_index("timestamp")
            common_idx = df_preds.index.intersection(df_ts.index)
            if len(common_idx) > 100:
                y_true = df_preds.loc[common_idx, "actual_min_do_72h"]
                y_pred = df_preds.loc[common_idx, "model_b_pred"]
                temps = df_ts.loc[common_idx, "water_temperature"]
                calibrator.fit_from_residuals(y_true, y_pred, temps)

        risk_model = EcologicalRiskModel(
            default_threshold_mg_L=self.threshold,
            calibrator=calibrator,
        )

        # -------------------------------------------------------------
        # 5. ENVELOPE GENERATOR: 2D RAIN-VS-TEMP GRID (envelope_generator)
        # -------------------------------------------------------------
        logger.info("Generating 2D Rainfall-versus-Temperature Storm Tolerance Envelope...")
        generator = StormToleranceEnvelopeGenerator(
            risk_model=risk_model,
            domain_checker=checker,
            operational_risk_limit=self.risk_limit,
            default_threshold_mg_L=self.threshold,
        )
        surface_data = generator.generate_surface_grid(
            rain_range_mm=(0.0, 70.0),
            temp_range_c=(1.0, 31.0),
            rain_steps=71,
            temp_steps=61,
        )

        # -------------------------------------------------------------
        # 6. EVENT-LEVEL BOOTSTRAP UNCERTAINTY (boundary_uncertainty)
        # -------------------------------------------------------------
        logger.info("Computing event-level block bootstrap uncertainty across independent storms...")
        boot_estimator = BoundaryUncertaintyEstimator(
            n_bootstraps=80,
            operational_risk_limit=self.risk_limit,
            default_threshold_mg_L=self.threshold,
        )
        uncertainty_data = boot_estimator.run_event_level_bootstrap(df_events)

        # -------------------------------------------------------------
        # 7. HISTORICAL STORM REPLAY (historical_storm_replay)
        # -------------------------------------------------------------
        logger.info("Executing event-by-event historical replay on held-out disturbances...")
        replay_engine = HistoricalStormReplay(
            risk_model=risk_model,
            domain_checker=checker,
            operational_risk_limit=self.risk_limit,
            default_threshold_mg_L=self.threshold,
        )
        df_replay, replay_summary = replay_engine.replay_events(
            df_events=df_events,
            df_timeseries=df_ts,
            threshold_mg_L=self.threshold,
            risk_limit=self.risk_limit,
        )
        df_replay.to_csv(self.reports_dir / "historical_storm_replay.csv", index=False)

        # -------------------------------------------------------------
        # 8. RISK CALIBRATION EVALUATION (risk_calibration)
        # -------------------------------------------------------------
        risk_calibrator = RiskCalibrator(operational_risk_limit=self.risk_limit)
        calib_results = risk_calibrator.evaluate_calibration_and_discrimination(
            y_true_binary=df_replay["actual_threshold_breach"].values,
            y_pred_probs=df_replay["predicted_risk_probability"].values,
        )

        # -------------------------------------------------------------
        # 9. VISUALIZATION & INTERACTIVE APP (envelope_visualization + ste_plotting)
        # -------------------------------------------------------------
        logger.info("Rendering 2D Rainfall-vs-Temperature publication figure & interactive application...")
        visualizer = EnvelopeVisualizer(output_dir=self.plots_dir)
        fig_path = visualizer.plot_static_envelope(
            surface_data=surface_data,
            uncertainty_data=uncertainty_data,
            df_events=df_replay,
            filename="storm_tolerance_envelope_2d_temp_rain.png",
        )
        app_path = visualizer.build_interactive_application(
            surface_data=surface_data,
            df_replay=df_replay,
            uncertainty_data=uncertainty_data,
            filename="storm_tolerance_envelope_app.html",
        )

        # Also generate multi-panel figures from Stage3Plotter
        plotter = Stage3Plotter(output_dir=self.plots_dir)
        evaluator = HistoricalSTEEvaluator(reports_dir=self.reports_dir)
        df_events_eval, contingency_summary = evaluator.evaluate_all_events()

        plotter.plot_1_storm_tolerance_envelope_2d(df_events_eval)
        plotter.plot_2_thermal_conditioning_envelopes()
        plotter.plot_3_antecedent_wetness_shift()
        plotter.plot_4_boundary_crossing_probability_curves()
        plotter.plot_5_time_to_trough_distribution(df_events_eval)
        plotter.plot_6_historical_event_envelope_backtest(df_events_eval, contingency_summary)
        plotter.plot_7_action_window_chronology_case_study(df_ts)
        plotter.plot_8_early_warning_reliability_diagram(df_events_eval)

        # -------------------------------------------------------------
        # 10. SAVE METADATA & PERSIST RESULTS
        # -------------------------------------------------------------
        metadata = {
            "stage": 3,
            "title": "AquaRehearsal-X Storm Tolerance Envelope",
            "station_id": STAGE3_DATA_CONFIG["station_id"],
            "station_name": STAGE3_DATA_CONFIG["station_name"],
            "data_period": "2023-01-01 to 2026-09-25",
            "total_storm_events": len(df_events),
            "non_overlapping_clean_events": n_clean,
            "overlapping_72h_events_flagged": n_overlapping,
            "default_do_threshold_mg_L": self.threshold,
            "operational_risk_limit": self.risk_limit,
            "supported_data_domain": checker.domain_summary,
            "calibration_metrics": calib_results,
            "replay_summary": replay_summary,
            "event_bootstrap_uncertainty": {
                "n_bootstraps": uncertainty_data["n_bootstrap_iterations"],
                "regime_counts": uncertainty_data["event_counts_by_regime"],
            },
            "deliverables": {
                "static_2d_envelope_figure": str(fig_path.name),
                "interactive_application": str(app_path.name),
                "replay_log_csv": "historical_storm_replay.csv",
            },
        }

        meta_path = self.models_dir / "stage3_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Saved complete Stage 3 metadata to %s", meta_path)

        # -------------------------------------------------------------
        # 11. PRINT STRUCTURED SCIENTIFIC SUMMARY
        # -------------------------------------------------------------
        print("\n" + "=" * 80)
        print("STAGE 3 — STORM TOLERANCE ENVELOPE (STE) VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Station:                 USGS {STAGE3_DATA_CONFIG['station_id']} ({STAGE3_DATA_CONFIG['station_name']})")
        print(f"Dataset Temporal Scope:  2023-01-01 to 2026-09-25 (32,807 hours)")
        print(f"Historical Storm Events: {len(df_events)} Total ({n_clean} Independent Non-Overlapping Units)")
        print(f"Active DO Risk Threshold: {self.threshold:.1f} mg/L (Configurable; PA DEP WWF Benchmark)")
        print(f"Operational Risk Limit:  {self.risk_limit*100:.0f}% Probability Contour")
        print("-" * 80)
        print("PROBABILISTIC CALIBRATION & DISCRIMINATION:")
        print(f"  • Brier Calibration Score:  {calib_results['brier_score']:.4f}")
        print(f"  • Sensitivity / Recall:     {calib_results['sensitivity_recall']:.3f} ({calib_results['sensitivity_recall']*100:.1f}%)")
        print(f"  • Specificity (Compliant):  {calib_results['specificity']:.3f} ({calib_results['specificity']*100:.1f}%)")
        print(f"  • Correct Warnings (TP):    {calib_results['true_positives']}")
        print(f"  • False Alarms (FP):        {calib_results['false_positives']}")
        print(f"  • Missed Events (FN):       {calib_results['false_negatives']}")
        print(f"  • Correct Safe Forecasts:   {calib_results['true_negatives']}")
        print("-" * 80)
        print("HISTORICAL REPLAY & LATENCY:")
        print(f"  • Median Lead Time to Nadir: {replay_summary['median_lead_time_hours']} hours" if replay_summary['median_lead_time_hours'] else "  • Median Lead Time: N/A")
        print(f"  • Supported Domain Bounds:   Temp: [{checker.min_temp_c:.1f}°C, {checker.max_temp_c:.1f}°C], Rain: [0, {checker.max_rainfall_mm:.1f} mm]")
        print("-" * 80)
        print("DELIVERABLES GENERATED:")
        print(f"  • 2D Publication Envelope:   data/reports/stage3/storm_tolerance_envelope_2d_temp_rain.png")
        print(f"  • Interactive Decision Tool: data/reports/stage3/storm_tolerance_envelope_app.html")
        print(f"  • Historical Replay Audit:   data/reports/stage3/historical_storm_replay.csv")
        print("=" * 80 + "\n")

        return metadata


if __name__ == "__main__":
    pipeline = Stage3Pipeline()
    pipeline.run()
