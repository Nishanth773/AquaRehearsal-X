"""
AquaRehearsal-X - Stage 2.5 Model Comparison Suite
Historical Depth + Real Precipitation Upgrade

Trains and rigorously compares two model architectures on the extended multi-year dataset:
- MODEL A: WATER-ONLY (144 features: DO, Temp, Discharge, Turbidity, Lags, Rolling Stats, Saturation, Seasonality)
- MODEL B: WATER + PRECIPITATION (Model A features + 12 explicit storm rainfall & surge features)

Research Question:
"Does direct precipitation information improve 72-hour minimum DO forecasting
beyond the existing water-quality/hydrologic information?"

Rigorous Validation:
- Identical chronological partitions (Train: 2023-01 to 2025-06; Val: 2025-07 to 2026-03; Test: 2026-04 to 2026-09)
- Identical target definition: min observed DO during (t, t + 72h]
- Identical random seeds and evaluation metrics
- Evaluated overall, during normal periods, and during storm disturbance events
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score

from src.config.stage2_5_settings import (
    STAGE2_5_SPLIT_CONFIG,
    STAGE2_5_TARGET_CONFIG,
    STAGE2_5_MODEL_CONFIG,
    STAGE2_5_MODELS_DIR,
    STAGE2_5_REPORTS_DIR,
    PRECIPITATION_METADATA,
)
from src.features.storm_features import StormFeatureBuilder
from src.features.target_builder import TargetBuilder
from src.models.forecaster import DissolvedOxygenForecaster
from src.models.uncertainty import QuantileForecaster, SplitConformalCalibrator
from src.models.ood_checker import InputDomainChecker
from src.models.evaluation import ModelEvaluator
from src.utils.logger import logger


class Stage2_5ModelComparison:
    """Manages training, uncertainty calibration, evaluation, and comparison of Model A vs Model B."""

    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.split_config = STAGE2_5_SPLIT_CONFIG
        self.target_config = STAGE2_5_TARGET_CONFIG
        self.model_config = STAGE2_5_MODEL_CONFIG
        self.models_dir = STAGE2_5_MODELS_DIR
        self.reports_dir = STAGE2_5_REPORTS_DIR

    def prepare_dataset(self) -> Tuple[pd.DataFrame, List[str], List[str], str]:
        """Loads data, generates target, and builds Model A and Model B feature sets."""
        logger.info("Loading extended dataset from %s...", self.data_path)
        df_raw = pd.read_csv(self.data_path)
        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], utc=True)
        df_raw = df_raw.sort_values("timestamp").reset_index(drop=True)

        # 1. Target Construction
        target_col = self.target_config["target_name"]
        target_builder = TargetBuilder(
            target_col="dissolved_oxygen",
            horizon_hours=self.target_config["forecast_horizon_hours"],
            min_valid_hours=self.target_config["min_valid_future_hours"],
        )
        df_with_target = target_builder.compute_72h_minimum_target(df_raw, output_col=target_col)

        # 2. Build Model A & Model B feature sets
        storm_builder = StormFeatureBuilder()
        df_features, model_a_cols, model_b_cols = storm_builder.build_model_feature_matrices(
            df_with_target, target_col=target_col
        )

        # 3. Filter valid targets
        df_valid = TargetBuilder.filter_valid_targets(df_features, target_col=target_col)
        return df_valid, model_a_cols, model_b_cols, target_col

    def run_comparison(self) -> Dict[str, Any]:
        """Executes full Model A vs Model B comparison on extended historical dataset."""
        df_valid, model_a_cols, model_b_cols, target_col = self.prepare_dataset()

        # Chronological splits
        train_start = pd.to_datetime(self.split_config["train_start"], utc=True)
        train_end = pd.to_datetime(self.split_config["train_end"], utc=True)
        val_start = pd.to_datetime(self.split_config["val_start"], utc=True)
        val_end = pd.to_datetime(self.split_config["val_end"], utc=True)
        test_start = pd.to_datetime(self.split_config["test_start"], utc=True)
        test_end = pd.to_datetime(self.split_config["test_end"], utc=True)

        train_mask = (df_valid.index >= train_start) & (df_valid.index <= train_end)
        val_mask = (df_valid.index >= val_start) & (df_valid.index <= val_end)
        test_mask = (df_valid.index >= test_start) & (df_valid.index <= test_end)

        df_train = df_valid[train_mask]
        df_val = df_valid[val_mask]
        df_test = df_valid[test_mask]

        logger.info(
            "Chronological Splitting (Multi-Year): Train=%d, Val=%d, Test=%d (Total Valid: %d)",
            len(df_train), len(df_val), len(df_test), len(df_valid)
        )

        y_train = df_train[target_col]
        y_val = df_val[target_col]
        y_test = df_test[target_col]

        # -------------------------------------------------------------
        # TRAIN MODEL A — WATER-ONLY
        # -------------------------------------------------------------
        logger.info("Training MODEL A (Water-Only: %d features)...", len(model_a_cols))
        model_a = DissolvedOxygenForecaster(
            model_params=self.model_config["lgbm_params"],
            early_stopping_rounds=self.model_config["lgbm_early_stopping_rounds"],
            random_seed=42,
        )
        model_a.fit(df_train[model_a_cols], y_train, df_val[model_a_cols], y_val)
        y_test_pred_a = model_a.predict(df_test[model_a_cols])

        # -------------------------------------------------------------
        # TRAIN MODEL B — WATER + PRECIPITATION
        # -------------------------------------------------------------
        logger.info("Training MODEL B (Water + Precipitation: %d features)...", len(model_b_cols))
        model_b = DissolvedOxygenForecaster(
            model_params=self.model_config["lgbm_params"],
            early_stopping_rounds=self.model_config["lgbm_early_stopping_rounds"],
            random_seed=42,
        )
        model_b.fit(df_train[model_b_cols], y_train, df_val[model_b_cols], y_val)
        y_test_pred_b = model_b.predict(df_test[model_b_cols])

        # -------------------------------------------------------------
        # UNCERTAINTY QUANTIFICATION (MODEL B)
        # -------------------------------------------------------------
        logger.info("Fitting Quantile Forecasters for Model B...")
        quantile_b = QuantileForecaster(
            quantiles=self.model_config["uncertainty_quantiles"],
            base_params=self.model_config["lgbm_params"],
            random_seed=42,
        )
        quantile_b.fit(df_train[model_b_cols], y_train)
        df_q_test_b = quantile_b.predict(df_test[model_b_cols])

        # Conformal Calibrator for Model B
        y_val_pred_b = model_b.predict(df_val[model_b_cols])
        conformal_b = SplitConformalCalibrator(nominal_coverage=self.model_config["conformal_nominal_coverage"])
        conformal_b.calibrate(y_val.to_numpy(), y_val_pred_b)
        conf_low_b, conf_up_b = conformal_b.predict_interval(y_test_pred_b)

        # -------------------------------------------------------------
        # EVALUATION: OVERALL TEST SET
        # -------------------------------------------------------------
        eval_a = ModelEvaluator.compute_metrics(y_test.to_numpy(), y_test_pred_a, model_name="Model A (Water-Only)")
        eval_b = ModelEvaluator.compute_metrics(y_test.to_numpy(), y_test_pred_b, model_name="Model B (Water + Precipitation)")

        # Coverage evaluation
        q10_b = df_q_test_b["q_0.10"].to_numpy()
        q90_b = df_q_test_b["q_0.90"].to_numpy()
        cov_q_b = SplitConformalCalibrator.evaluate_coverage(y_test.to_numpy(), q10_b, q90_b)
        cov_conf_b = SplitConformalCalibrator.evaluate_coverage(y_test.to_numpy(), conf_low_b, conf_up_b)

        # -------------------------------------------------------------
        # STORM VS NORMAL PERIOD EVALUATION
        # -------------------------------------------------------------
        # Load historical storm events to define storm periods
        events_csv = self.reports_dir / "historical_storm_events.csv"
        df_events = pd.read_csv(events_csv)
        df_events["event_start"] = pd.to_datetime(df_events["event_start"], utc=True)

        # A timestamp is defined as 'storm_period' if within [-12h, +72h] of any storm event onset
        storm_mask = np.zeros(len(df_test), dtype=bool)
        test_index = df_test.index
        for _, ev in df_events.iterrows():
            e_t = ev["event_start"]
            ev_mask = (test_index >= e_t - pd.Timedelta(hours=12)) & (test_index <= e_t + pd.Timedelta(hours=72))
            storm_mask = storm_mask | ev_mask

        normal_mask = ~storm_mask

        # Metrics during Storm Periods
        y_test_arr = y_test.to_numpy()
        storm_eval_a = ModelEvaluator.compute_metrics(y_test_arr[storm_mask], y_test_pred_a[storm_mask], model_name="Model A (Storm Periods)")
        storm_eval_b = ModelEvaluator.compute_metrics(y_test_arr[storm_mask], y_test_pred_b[storm_mask], model_name="Model B (Storm Periods)")

        # Metrics during Normal Periods
        normal_eval_a = ModelEvaluator.compute_metrics(y_test_arr[normal_mask], y_test_pred_a[normal_mask], model_name="Model A (Normal Periods)")
        normal_eval_b = ModelEvaluator.compute_metrics(y_test_arr[normal_mask], y_test_pred_b[normal_mask], model_name="Model B (Normal Periods)")

        # -------------------------------------------------------------
        # STORM-EVENT BACKTESTING: MODEL A VS MODEL B
        # -------------------------------------------------------------
        test_events = df_events[df_events["partition"] == "TEST"].copy()
        event_backtest_records = []

        for _, ev in test_events.iterrows():
            ev_start = ev["event_start"]
            valid_idx = df_valid.index[df_valid.index <= ev_start]
            if len(valid_idx) == 0:
                continue
            p_time = valid_idx[-1]

            actual_min = df_valid.loc[p_time, target_col]
            if pd.isna(actual_min):
                continue

            feats_a = df_valid.loc[[p_time], model_a_cols]
            feats_b = df_valid.loc[[p_time], model_b_cols]

            pred_a = float(model_a.predict(feats_a)[0])
            pred_b = float(model_b.predict(feats_b)[0])

            err_a = pred_a - actual_min
            err_b = pred_b - actual_min

            event_backtest_records.append({
                "event_id": ev["event_id"],
                "event_start": ev_start.isoformat(),
                "peak_discharge_cfs": ev["peak_discharge_cfs"],
                "cumulative_rainfall_mm": ev["cumulative_rainfall_mm"],
                "pre_event_do_mg_L": ev["pre_event_do_mg_L"],
                "actual_min_do_72h": round(actual_min, 2),
                "model_a_pred": round(pred_a, 2),
                "model_a_abs_error": round(abs(err_a), 2),
                "model_b_pred": round(pred_b, 2),
                "model_b_abs_error": round(abs(err_b), 2),
                "delta_improvement_b_vs_a": round(abs(err_a) - abs(err_b), 2),
            })

        df_storm_backtest = pd.DataFrame(event_backtest_records)
        df_storm_backtest.to_csv(self.reports_dir / "storm_event_model_comparison.csv", index=False)

        # -------------------------------------------------------------
        # FEATURE IMPORTANCE (MODEL B)
        # -------------------------------------------------------------
        df_imp_b = model_b.get_feature_importance()
        df_imp_b.to_csv(self.reports_dir / "model_b_feature_importance.csv", index=False)

        precip_imp = df_imp_b[df_imp_b["feature"].str.contains("rain|precipitation|surge")]

        # -------------------------------------------------------------
        # UPDATE INPUT DOMAIN CHECKER WITH RAINFALL RANGES
        # -------------------------------------------------------------
        domain_checker = InputDomainChecker(
            key_variables=["dissolved_oxygen", "water_temperature", "discharge", "turbidity", "rain_1h", "rain_roll_24h"]
        )
        domain_checker.fit(df_train[model_b_cols])
        domain_checker.save(self.models_dir / "domain_ranges_stage2_5.json")

        # -------------------------------------------------------------
        # BUILD STRUCTURED COMPARISON TABLE
        # -------------------------------------------------------------
        comp_rows = [
            {
                "EVALUATION REGIME": "Overall Unseen Test Set (Full 2026 Season)",
                "MODEL": "Model A (Water-Only)",
                "MAE (mg/L)": eval_a["mae"],
                "RMSE (mg/L)": eval_a["rmse"],
                "R²": eval_a["r2"],
                "Median AE (mg/L)": eval_a["median_ae"],
                "Within +/-1.0 mg/L (%)": eval_a["pct_within_1_0_mg_L"],
                "Samples": eval_a["n_samples"],
            },
            {
                "EVALUATION REGIME": "Overall Unseen Test Set (Full 2026 Season)",
                "MODEL": "Model B (Water + Precipitation)",
                "MAE (mg/L)": eval_b["mae"],
                "RMSE (mg/L)": eval_b["rmse"],
                "R²": eval_b["r2"],
                "Median AE (mg/L)": eval_b["median_ae"],
                "Within +/-1.0 mg/L (%)": eval_b["pct_within_1_0_mg_L"],
                "Samples": eval_b["n_samples"],
            },
            {
                "EVALUATION REGIME": "Storm/Disturbance Periods Only",
                "MODEL": "Model A (Water-Only)",
                "MAE (mg/L)": storm_eval_a["mae"],
                "RMSE (mg/L)": storm_eval_a["rmse"],
                "R²": storm_eval_a["r2"],
                "Median AE (mg/L)": storm_eval_a["median_ae"],
                "Within +/-1.0 mg/L (%)": storm_eval_a["pct_within_1_0_mg_L"],
                "Samples": storm_eval_a["n_samples"],
            },
            {
                "EVALUATION REGIME": "Storm/Disturbance Periods Only",
                "MODEL": "Model B (Water + Precipitation)",
                "MAE (mg/L)": storm_eval_b["mae"],
                "RMSE (mg/L)": storm_eval_b["rmse"],
                "R²": storm_eval_b["r2"],
                "Median AE (mg/L)": storm_eval_b["median_ae"],
                "Within +/-1.0 mg/L (%)": storm_eval_b["pct_within_1_0_mg_L"],
                "Samples": storm_eval_b["n_samples"],
            },
            {
                "EVALUATION REGIME": "Normal / Baseflow Periods Only",
                "MODEL": "Model A (Water-Only)",
                "MAE (mg/L)": normal_eval_a["mae"],
                "RMSE (mg/L)": normal_eval_a["rmse"],
                "R²": normal_eval_a["r2"],
                "Median AE (mg/L)": normal_eval_a["median_ae"],
                "Within +/-1.0 mg/L (%)": normal_eval_a["pct_within_1_0_mg_L"],
                "Samples": normal_eval_a["n_samples"],
            },
            {
                "EVALUATION REGIME": "Normal / Baseflow Periods Only",
                "MODEL": "Model B (Water + Precipitation)",
                "MAE (mg/L)": normal_eval_b["mae"],
                "RMSE (mg/L)": normal_eval_b["rmse"],
                "R²": normal_eval_b["r2"],
                "Median AE (mg/L)": normal_eval_b["median_ae"],
                "Within +/-1.0 mg/L (%)": normal_eval_b["pct_within_1_0_mg_L"],
                "Samples": normal_eval_b["n_samples"],
            },
        ]
        df_comp = pd.DataFrame(comp_rows)
        df_comp.to_csv(self.reports_dir / "stage2_5_model_comparison_metrics.csv", index=False)

        # Save artifacts
        model_a.save(self.models_dir / "model_water_only.joblib")
        model_b.save(self.models_dir / "model_water_plus_precipitation.joblib")
        quantile_b.save(self.models_dir)

        # Save test predictions table
        df_test_preds = pd.DataFrame({
            "timestamp": df_test.index,
            "actual_min_do_72h": y_test.values,
            "model_a_pred": y_test_pred_a,
            "model_b_pred": y_test_pred_b,
            "model_b_q10": q10_b,
            "model_b_q90": q90_b,
            "model_b_conformal_lower": conf_low_b,
            "model_b_conformal_upper": conf_up_b,
            "is_storm_period": storm_mask,
        })
        df_test_preds.to_csv(self.reports_dir / "stage2_5_test_predictions.csv", index=False)

        # Structured metadata
        metadata = {
            "stage": 2.5,
            "models": ["Model A (Water-Only)", "Model B (Water + Precipitation)"],
            "dataset_rows": len(df_valid),
            "split_samples": {"train": len(df_train), "val": len(df_val), "test": len(df_test)},
            "features_count": {"model_a": len(model_a_cols), "model_b": len(model_b_cols)},
            "metrics": {
                "overall": {"model_a": eval_a, "model_b": eval_b},
                "storm_periods": {"model_a": storm_eval_a, "model_b": storm_eval_b},
                "normal_periods": {"model_a": normal_eval_a, "model_b": normal_eval_b},
            },
            "uncertainty_b": {
                "quantile_80_coverage_pct": cov_q_b["coverage_pct"],
                "quantile_80_width": cov_q_b["mean_width_mg_L"],
                "conformal_80_coverage_pct": cov_conf_b["coverage_pct"],
                "conformal_80_width": cov_conf_b["mean_width_mg_L"],
            },
            "precipitation_metadata": PRECIPITATION_METADATA,
        }
        with open(self.models_dir / "stage2_5_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logger.info("Stage 2.5 Model Comparison Complete.")
        return {
            "comparison_df": df_comp,
            "storm_backtest_df": df_storm_backtest,
            "feature_importance_b": df_imp_b,
            "metadata": metadata,
            "df_test": df_test,
            "y_test_pred_a": y_test_pred_a,
            "y_test_pred_b": y_test_pred_b,
            "q10_b": q10_b,
            "q90_b": q90_b,
        }
