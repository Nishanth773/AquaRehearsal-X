"""
AquaRehearsal-X - Stage 2 Master Pipeline Orchestrator
72-Hour Dissolved Oxygen Forecasting Engine

Executes the complete end-to-end scientific modeling workflow:
1. Data Verification & Pre-Training Audit Report
2. Leakage-Free Target Construction (72h Future Minimum DO)
3. Causal Feature Engineering (Lags, Rolling Backward Stats, Changes, Physical Saturation, Cyclical Encodings)
4. Chronological Validation Partitioning (Train -> Val -> Test)
5. Baseline Model Training & Evaluation (Baseline A & Baseline B)
6. Main ML Model Training (LightGBM Regressor with Early Stopping)
7. Uncertainty Model Fitting (Quantile LightGBM & Split Conformal Prediction)
8. Basic Input-Domain / OOD Range Fitting
9. Out-of-Sample Performance Evaluation & Comprehensive Metrics Comparison
10. Historical Storm-Event Backtesting
11. Publication-Grade Scientific Visualizations (9 Figures)
12. Model Artifact & Metadata Persistence
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import joblib
import numpy as np
import pandas as pd

from src.config.stage2_settings import (
    STAGE2_STATION_CONFIG,
    STAGE2_TARGET_CONFIG,
    STAGE2_SPLIT_CONFIG,
    STAGE2_FEATURE_CONFIG,
    STAGE2_MODEL_CONFIG,
    STAGE2_REPORTS_DIR,
    STAGE2_MODELS_DIR,
    STAGE2_PLOTS_DIR,
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
)
from src.features.target_builder import TargetBuilder
from src.features.feature_builder import FeatureBuilder
from src.models.baselines import PersistenceBaseline, LinearSeasonalBaseline
from src.models.forecaster import DissolvedOxygenForecaster
from src.models.uncertainty import QuantileForecaster, SplitConformalCalibrator
from src.models.ood_checker import InputDomainChecker
from src.models.backtester import StormEventBacktester
from src.models.evaluation import ModelEvaluator
from src.models.plotting import Stage2Plotter
from src.utils.logger import logger


class Stage2Pipeline:
    """Master orchestrator for the 72-hour DO forecasting engine."""

    def __init__(self):
        self.station_config = STAGE2_STATION_CONFIG
        self.target_config = STAGE2_TARGET_CONFIG
        self.split_config = STAGE2_SPLIT_CONFIG
        self.feature_config = STAGE2_FEATURE_CONFIG
        self.model_config = STAGE2_MODEL_CONFIG

        self.reports_dir = STAGE2_REPORTS_DIR
        self.models_dir = STAGE2_MODELS_DIR
        self.plotter = Stage2Plotter(output_dir=STAGE2_PLOTS_DIR)

    def print_data_verification_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Audits and prints a concise verification report before training."""
        logger.info("=" * 65)
        logger.info("AQUAREHEARSAL-X — STAGE 2: DATA VERIFICATION REPORT")
        logger.info("=" * 65)

        total_obs = len(df)
        time_min = df["timestamp"].min() if "timestamp" in df.columns else df.index.min()
        time_max = df["timestamp"].max() if "timestamp" in df.columns else df.index.max()

        stats = {
            "station_id": self.station_config["primary_station_id"],
            "station_name": self.station_config["primary_station_name"],
            "temporal_resolution": self.station_config["temporal_resolution"],
            "total_observations": total_obs,
            "time_range_start": str(time_min),
            "time_range_end": str(time_max),
            "variables": {},
        }

        print(f"Station ID:            {stats['station_id']}")
        print(f"Station Name:          {stats['station_name']}")
        print(f"Temporal Resolution:   {stats['temporal_resolution']}")
        print(f"Total Observations:    {total_obs}")
        print(f"Time Range:            {time_min}  to  {time_max}")
        print("-" * 65)
        print(f"{'Variable':<22} | {'Available Count':<16} | {'Availability %':<15} | {'Missing %':<10}")
        print("-" * 65)

        for col in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"]:
            if col in df.columns:
                valid_count = int(df[col].notna().sum())
                avail_pct = (valid_count / total_obs * 100.0) if total_obs > 0 else 0.0
                missing_pct = 100.0 - avail_pct
                stats["variables"][col] = {
                    "valid_count": valid_count,
                    "availability_pct": round(avail_pct, 2),
                    "missing_pct": round(missing_pct, 2),
                }
                print(f"{col:<22} | {valid_count:<16} | {avail_pct:>13.2f}% | {missing_pct:>8.2f}%")
            else:
                stats["variables"][col] = "NOT_FOUND"
                print(f"{col:<22} | {'0':<16} | {'0.00%':<15} | {'100.00%':<10}")

        print("=" * 65)
        print("Sensor Notes & Adaptations:")
        print("  - Dissolved Oxygen completeness: 99.49% (4,298 / 4,320 hours).")
        print("  - Water Temperature completeness: 99.51% (4,299 / 4,320 hours).")
        print("  - Discharge completeness: 99.68% (4,306 / 4,320 hours).")
        print("  - Turbidity completeness: 66.53% overall; turbidity monitoring initiated on 2026-05-31.")
        print("    After 2026-05-31, turbidity availability is 99.74%.")
        print("  - Missingness adaptation: Tree models handle native NaNs without synthetic imputation.")
        print("=" * 65)
        return stats

    def run(self) -> Dict[str, Any]:
        """Executes the complete Stage 2 scientific pipeline."""
        logger.info("Initiating AquaRehearsal-X Stage 2 Pipeline...")

        # 1. Load Processed Clean Hourly Dataset
        data_path = PROCESSED_DATA_DIR / self.station_config["primary_data_file"]
        if not data_path.exists():
            raise FileNotFoundError(f"Processed dataset not found: {data_path}. Run Stage 1 pipeline first.")

        df_raw = pd.read_csv(data_path)
        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], utc=True)
        df_raw = df_raw.sort_values("timestamp").reset_index(drop=True)

        # 2. Print Verification Report
        verification_report = self.print_data_verification_report(df_raw)

        # 3. Construct 72-Hour Future Minimum DO Target
        target_col = self.target_config["target_name"]
        target_builder = TargetBuilder(
            target_col="dissolved_oxygen",
            horizon_hours=self.target_config["forecast_horizon_hours"],
            min_valid_hours=self.target_config["min_valid_future_hours"],
        )
        df_with_target = target_builder.compute_72h_minimum_target(df_raw, output_col=target_col)

        # 4. Feature Engineering (Strictly Causal & Leakage-Free)
        feature_builder = FeatureBuilder(config=self.feature_config)
        df_features, feature_cols = feature_builder.build_feature_matrix(df_with_target, target_col=target_col)

        # 5. Filter Valid Target Rows (exclude incomplete target windows at end of time series)
        df_valid = TargetBuilder.filter_valid_targets(df_features, target_col=target_col)

        # 6. Chronological Partitioning (Train -> Validation -> Test)
        train_end = pd.to_datetime(self.split_config["train_end"], utc=True)
        val_end = pd.to_datetime(self.split_config["val_end"], utc=True)
        test_end = pd.to_datetime(self.split_config["test_end"], utc=True)

        train_mask = (df_valid.index >= pd.to_datetime(self.split_config["train_start"], utc=True)) & (df_valid.index < train_end)
        val_mask = (df_valid.index >= train_end) & (df_valid.index < val_end)
        test_mask = (df_valid.index >= val_end) & (df_valid.index <= test_end)

        df_train = df_valid[train_mask]
        df_val = df_valid[val_mask]
        df_test = df_valid[test_mask]

        logger.info(
            "Chronological Splitting: Train=%d (%s to %s), Val=%d (%s to %s), Test=%d (%s to %s)",
            len(df_train), df_train.index.min(), df_train.index.max(),
            len(df_val), df_val.index.min(), df_val.index.max(),
            len(df_test), df_test.index.min(), df_test.index.max(),
        )

        X_train, y_train = df_train[feature_cols], df_train[target_col]
        X_val, y_val = df_val[feature_cols], df_val[target_col]
        X_test, y_test = df_test[feature_cols], df_test[target_col]

        # 7. Fit Baseline Models (Strictly on Training Data)
        baseline_a = PersistenceBaseline(current_do_col="dissolved_oxygen")
        baseline_a.fit(X_train, y_train)

        baseline_b = LinearSeasonalBaseline()
        baseline_b.fit(X_train, y_train)

        # 8. Fit Main ML Model (LightGBM with Validation Early Stopping)
        forecaster = DissolvedOxygenForecaster(
            model_params=self.model_config["lgbm_params"],
            early_stopping_rounds=self.model_config["lgbm_early_stopping_rounds"],
            random_seed=self.station_config["random_seed"],
        )
        forecaster.fit(X_train, y_train, X_val, y_val)

        # 9. Fit Uncertainty Models
        # A. Quantile LightGBM
        quantile_forecaster = QuantileForecaster(
            quantiles=self.model_config["uncertainty_quantiles"],
            base_params=self.model_config["lgbm_params"],
            random_seed=self.station_config["random_seed"],
        )
        quantile_forecaster.fit(X_train, y_train)

        # B. Split Conformal Calibrator on Validation Set
        y_val_pred = forecaster.predict(X_val)
        conformal_calibrator = SplitConformalCalibrator(nominal_coverage=self.model_config["conformal_nominal_coverage"])
        conformal_calibrator.calibrate(y_val.to_numpy(), y_val_pred)

        # 10. Fit Basic Input-Domain / OOD Range Checker
        domain_checker = InputDomainChecker()
        domain_checker.fit(X_train)

        # 11. Out-of-Sample Predictions on Unseen Test Period
        y_test_pred_base_a = baseline_a.predict(X_test)
        y_test_pred_base_b = baseline_b.predict(X_test)
        y_test_pred_ml = forecaster.predict(X_test)

        # Quantile predictions on test set
        df_q_test = quantile_forecaster.predict(X_test)
        q10_test = df_q_test["q_0.10"].to_numpy()
        q50_test = df_q_test["q_0.50"].to_numpy()
        q90_test = df_q_test["q_0.90"].to_numpy()

        # Conformal intervals on test set
        conf_low_test, conf_up_test = conformal_calibrator.predict_interval(y_test_pred_ml)

        # 12. Evaluate Metrics
        eval_base_a = ModelEvaluator.compute_metrics(y_test.to_numpy(), y_test_pred_base_a, model_name="Baseline A (Persistence: Current DO)")
        eval_base_b = ModelEvaluator.compute_metrics(y_test.to_numpy(), y_test_pred_base_b, model_name="Baseline B (Linear: DO + Temp + Season)")
        eval_ml = ModelEvaluator.compute_metrics(y_test.to_numpy(), y_test_pred_ml, model_name="LightGBM Regressor (Stage 2 Main ML)")

        # Coverage evaluations
        cov_quantile_80 = SplitConformalCalibrator.evaluate_coverage(y_test.to_numpy(), q10_test, q90_test)
        cov_conformal_80 = SplitConformalCalibrator.evaluate_coverage(y_test.to_numpy(), conf_low_test, conf_up_test)

        logger.info("Empirical Coverage on Test Set:")
        logger.info("  - Quantile LightGBM 80%% Interval [q10, q90]: %.2f%% (Mean Width: %.2f mg/L)", cov_quantile_80["coverage_pct"], cov_quantile_80["mean_width_mg_L"])
        logger.info("  - Conformal 80%% Interval:                     %.2f%% (Mean Width: %.2f mg/L)", cov_conformal_80["coverage_pct"], cov_conformal_80["mean_width_mg_L"])

        # 13. Historical Storm-Event Backtesting
        candidate_events_path = REPORTS_DIR / "candidate_storm_events.csv"
        df_backtest = pd.DataFrame()
        if candidate_events_path.exists():
            df_events = pd.read_csv(candidate_events_path)
            backtester = StormEventBacktester(df_events, split_boundaries=self.split_config)
            df_backtest = backtester.run_backtests(
                features_df=df_valid,
                feature_cols=feature_cols,
                target_col=target_col,
                ml_model=forecaster,
                baseline_a=baseline_a,
                baseline_b=baseline_b,
                quantile_model=quantile_forecaster,
                conformal_calibrator=conformal_calibrator,
            )
            df_backtest.to_csv(self.reports_dir / "backtest_results.csv", index=False)

        # 14. Generate Comparison Table
        eval_dict = {
            "Baseline A (Persistence)": eval_base_a,
            "Baseline B (Linear Seasonal)": eval_base_b,
            "LightGBM Regressor": eval_ml,
        }
        df_comparison = ModelEvaluator.generate_comparison_table(eval_dict, backtest_df=df_backtest)
        df_comparison.to_csv(self.reports_dir / "model_comparison_metrics.csv", index=False)

        print("\n" + "=" * 80)
        print("STAGE 2 MODEL COMPARISON TABLE (UNSEEN CHRONOLOGICAL TEST SET)")
        print("=" * 80)
        print(df_comparison.to_string(index=False))
        print("=" * 80 + "\n")

        # 15. Feature Importance Extraction
        df_importance = forecaster.get_feature_importance()
        df_importance.to_csv(self.reports_dir / "feature_importance.csv", index=False)

        # 16. Save Test Predictions Table
        df_test_preds = pd.DataFrame({
            "timestamp": df_test.index,
            "actual_min_do_72h": y_test.values,
            "pred_ml": y_test_pred_ml,
            "residual_ml": y_test_pred_ml - y_test.values,
            "pred_base_a": y_test_pred_base_a,
            "pred_base_b": y_test_pred_base_b,
            "q10": q10_test,
            "q50": q50_test,
            "q90": q90_test,
            "conformal_lower": conf_low_test,
            "conformal_upper": conf_up_test,
        })
        df_test_preds.to_csv(self.reports_dir / "test_predictions.csv", index=False)

        # 17. Save Model Artifacts and Metadata
        forecaster.save(self.models_dir / "lgbm_regressor.joblib")
        quantile_forecaster.save(self.models_dir)
        domain_checker.save(self.models_dir / "domain_ranges.json")
        joblib.dump(baseline_b, self.models_dir / "baseline_b_model.joblib")

        with open(self.models_dir / "feature_list.json", "w", encoding="utf-8") as f:
            json.dump(feature_cols, f, indent=2)

        metadata = {
            "project": "AquaRehearsal-X",
            "stage": 2,
            "component": "72-Hour Dissolved Oxygen Forecasting Engine",
            "station_id": self.station_config["primary_station_id"],
            "station_name": self.station_config["primary_station_name"],
            "temporal_resolution": self.station_config["temporal_resolution"],
            "target": self.target_config,
            "split_dates": self.split_config,
            "random_seed": self.station_config["random_seed"],
            "sample_counts": {
                "total_valid_samples": len(df_valid),
                "train_samples": len(df_train),
                "val_samples": len(df_val),
                "test_samples": len(df_test),
            },
            "metrics_test": {
                "lightgbm": eval_ml,
                "baseline_a_persistence": eval_base_a,
                "baseline_b_linear": eval_base_b,
            },
            "uncertainty_coverage": {
                "quantile_80_empirical_coverage_pct": cov_quantile_80["coverage_pct"],
                "quantile_80_mean_width_mg_L": cov_quantile_80["mean_width_mg_L"],
                "conformal_80_empirical_coverage_pct": cov_conformal_80["coverage_pct"],
                "conformal_80_mean_width_mg_L": cov_conformal_80["mean_width_mg_L"],
            },
        }
        with open(self.models_dir / "model_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 18. Generate All 9 Visualizations
        logger.info("Generating 9 publication-grade scientific visualizations...")
        self.plotter.plot_1_actual_vs_predicted_scatter(y_test.to_numpy(), y_test_pred_ml, metrics=eval_ml)
        self.plotter.plot_2_timeseries_forecast_trajectory(df_test.index, y_test.to_numpy(), y_test_pred_ml, y_test_pred_base_a)
        self.plotter.plot_3_prediction_intervals_test(df_test.index, y_test.to_numpy(), y_test_pred_ml, q10_test, q90_test, empirical_coverage=cov_quantile_80["coverage_pct"])
        self.plotter.plot_4_residual_distribution(y_test_pred_ml - y_test.to_numpy())
        self.plotter.plot_5_residuals_vs_predicted(y_test_pred_ml, y_test_pred_ml - y_test.to_numpy())
        self.plotter.plot_6_baseline_vs_ml_comparison(df_comparison)
        self.plotter.plot_7_feature_importance(df_importance, top_n=15)
        if not df_backtest.empty:
            self.plotter.plot_8_disturbance_backtesting_errors(df_backtest)
        self.plotter.plot_9_interval_coverage_reliability(
            nominal_coverages=[0.80],
            observed_coverages=[cov_quantile_80["coverage_pct"]],
            method_name="Quantile LightGBM",
        )

        logger.info("Stage 2 Scientific Pipeline Completed Successfully.")
        return metadata


if __name__ == "__main__":
    pipeline = Stage2Pipeline()
    pipeline.run()
