"""
AquaRehearsal-X - Evaluation Metrics and Model Comparison
72-Hour Dissolved Oxygen Forecasting Engine

Calculates comprehensive regression metrics:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- R² (Coefficient of Determination)
- Median Absolute Error
- Accuracy within tolerance envelopes: percentage within +/- 0.5 mg/L, +/- 1.0 mg/L
- Residual error distribution (10th, 25th, 50th, 75th, 90th percentiles)
- Disturbance event error breakdown

Strict Scientific Mandate:
- Never cherry-pick successful periods.
- Report all metrics on the strictly unseen chronological test set.
"""

from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score

from src.utils.logger import logger


class ModelEvaluator:
    """Computes comprehensive regression metrics and baseline comparisons."""

    @staticmethod
    def compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str = "Model",
    ) -> Dict[str, Any]:
        """Calculates standard and domain-specific regression metrics."""
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)

        mask = np.isfinite(y_true) & np.isfinite(y_pred)
        yt = y_true[mask]
        yp = y_pred[mask]
        n_samples = len(yt)

        if n_samples == 0:
            return {
                "model_name": model_name,
                "n_samples": 0,
                "mae": np.nan,
                "rmse": np.nan,
                "r2": np.nan,
                "median_ae": np.nan,
                "pct_within_0_5_mg_L": np.nan,
                "pct_within_1_0_mg_L": np.nan,
            }

        residuals = yp - yt
        abs_errors = np.abs(residuals)

        mae = float(mean_absolute_error(yt, yp))
        rmse = float(root_mean_squared_error(yt, yp))
        r2 = float(r2_score(yt, yp))
        med_ae = float(np.median(abs_errors))

        pct_within_05 = float(np.mean(abs_errors <= 0.5) * 100.0)
        pct_within_10 = float(np.mean(abs_errors <= 1.0) * 100.0)

        # Percentiles of residuals
        res_p10 = float(np.percentile(residuals, 10))
        res_p25 = float(np.percentile(residuals, 25))
        res_p50 = float(np.percentile(residuals, 50))
        res_p75 = float(np.percentile(residuals, 75))
        res_p90 = float(np.percentile(residuals, 90))

        return {
            "model_name": model_name,
            "n_samples": n_samples,
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 4),
            "median_ae": round(med_ae, 3),
            "pct_within_0_5_mg_L": round(pct_within_05, 2),
            "pct_within_1_0_mg_L": round(pct_within_10, 2),
            "residual_p10": round(res_p10, 3),
            "residual_p25": round(res_p25, 3),
            "residual_median_p50": round(res_p50, 3),
            "residual_p75": round(res_p75, 3),
            "residual_p90": round(res_p90, 3),
        }

    @classmethod
    def generate_comparison_table(
        cls,
        eval_dict: Dict[str, Dict[str, Any]],
        backtest_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Creates structured comparison table across models.

        Args:
            eval_dict: Dict mapping model key to metrics dict.
            backtest_df: DataFrame from StormEventBacktester (optional).
        """
        rows = []
        for key, m in eval_dict.items():
            model_name = m.get("model_name", key)

            # Compute disturbance performance on TEST events if backtest results provided
            dist_mae = np.nan
            if backtest_df is not None and not backtest_df.empty:
                test_events = backtest_df[backtest_df["partition"] == "TEST"]
                if not test_events.empty:
                    if "ml" in key.lower() or "lightgbm" in key.lower():
                        dist_mae = float(test_events["abs_error_ml"].mean())
                    elif "baseline_a" in key.lower() or "persistence" in key.lower():
                        dist_mae = float(test_events["abs_error_base_a"].mean())
                    elif "baseline_b" in key.lower() or "linear" in key.lower():
                        dist_mae = float(test_events["abs_error_base_b"].mean())

            rows.append({
                "MODEL": model_name,
                "MAE (mg/L)": m.get("mae"),
                "RMSE (mg/L)": m.get("rmse"),
                "R²": m.get("r2"),
                "Median AE (mg/L)": m.get("median_ae"),
                "Within +/-0.5 mg/L (%)": m.get("pct_within_0_5_mg_L"),
                "Within +/-1.0 mg/L (%)": m.get("pct_within_1_0_mg_L"),
                "NUMBER OF TEST SAMPLES": m.get("n_samples"),
                "DISTURBANCE-EVENT MAE (TEST)": round(dist_mae, 3) if np.isfinite(dist_mae) else "N/A",
            })

        df_comp = pd.DataFrame(rows)
        return df_comp
