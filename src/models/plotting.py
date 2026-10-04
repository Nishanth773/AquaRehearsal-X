"""
AquaRehearsal-X - Stage 2 Visualization Suite
72-Hour Dissolved Oxygen Forecasting Engine

Generates 9 publication-grade scientific visualizations saved under data/reports/stage2/:
1. Actual vs predicted minimum DO
2. Time-series forecast examples
3. Prediction interval vs actual target
4. Residual distribution
5. Residual vs predicted value
6. Baseline vs ML performance
7. Feature importance (model feature importance)
8. Historical disturbance-event predictions
9. Prediction coverage / reliability
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.config.stage2_settings import STAGE2_PLOTS_DIR
from src.utils.logger import logger

# Set aesthetic defaults
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})


class Stage2Plotter:
    """Generates all 9 scientific figures for Stage 2 evaluation."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or STAGE2_PLOTS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_1_actual_vs_predicted_scatter(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        metrics: Dict[str, Any],
        filename: str = "1_actual_vs_predicted_scatter.png",
    ):
        """Plot 1: Actual vs Predicted Minimum DO Scatter Plot with 1:1 Identity Line."""
        fig, ax = plt.subplots(figsize=(7, 6))

        ax.scatter(y_true, y_pred, color="#1f77b4", alpha=0.5, edgecolors="none", s=25, label="Test Observations")

        # 1:1 Identity Line
        min_val = min(np.nanmin(y_true), np.nanmin(y_pred)) - 0.5
        max_val = max(np.nanmax(y_true), np.nanmax(y_pred)) + 0.5
        ax.plot([min_val, max_val], [min_val, max_val], color="#d62728", linestyle="--", linewidth=1.8, label="1:1 Perfect Forecast")

        # Linear trend
        z = np.polyfit(y_true, y_pred, 1)
        p = np.poly1d(z)
        x_vals = np.linspace(min_val, max_val, 100)
        ax.plot(x_vals, p(x_vals), color="#2ca02c", linestyle="-", linewidth=1.5, label=f"Fit: y = {z[0]:.2f}x + {z[1]:.2f}")

        ax.set_xlim(min_val, max_val)
        ax.set_ylim(min_val, max_val)
        ax.set_xlabel("Actual 72-Hour Minimum Dissolved Oxygen (mg/L)")
        ax.set_ylabel("Predicted 72-Hour Minimum Dissolved Oxygen (mg/L)")
        ax.set_title("Actual vs. Predicted Future 72-Hour Minimum DO (Test Period)")

        # Annotation box
        mae = metrics.get("mae", 0.0)
        rmse = metrics.get("rmse", 0.0)
        r2 = metrics.get("r2", 0.0)
        textstr = f"MAE: {mae:.2f} mg/L\nRMSE: {rmse:.2f} mg/L\nR²: {r2:.3f}\nSamples: {len(y_true)}"
        props = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.85, edgecolor="#cccccc")
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10, verticalalignment="top", bbox=props)

        ax.legend(loc="lower right", framealpha=0.9)
        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_2_timeseries_forecast_trajectory(
        self,
        test_index: pd.DatetimeIndex,
        y_true: np.ndarray,
        y_pred_ml: np.ndarray,
        y_pred_base_a: np.ndarray,
        filename: str = "2_timeseries_forecast_trajectory.png",
    ):
        """Plot 2: Time-Series Forecast Examples across Unseen Test Period."""
        fig, ax = plt.subplots(figsize=(12, 5.5))

        ax.plot(test_index, y_true, color="#000000", linewidth=1.8, label="Actual 72h Future Min DO (Observed Ground Truth)")
        ax.plot(test_index, y_pred_ml, color="#1f77b4", linewidth=1.5, alpha=0.9, label="LightGBM 72h Min DO Forecast")
        ax.plot(test_index, y_pred_base_a, color="#ff7f0e", linestyle=":", linewidth=1.2, alpha=0.7, label="Baseline A (Persistence: Current DO)")

        # Ecological threshold lines (for context)
        ax.axhline(5.0, color="#d62728", linestyle="--", linewidth=1.0, alpha=0.7, label="Ecological Benchmark (5.0 mg/L)")

        ax.set_xlabel("Prediction Timestamp (UTC)")
        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title("Time-Series Forecast Trajectory: LightGBM vs. Persistence vs. Ground Truth")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))

        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_3_prediction_intervals_test(
        self,
        test_index: pd.DatetimeIndex,
        y_true: np.ndarray,
        y_pred_ml: np.ndarray,
        q_lower: np.ndarray,
        q_upper: np.ndarray,
        empirical_coverage: float,
        filename: str = "3_prediction_intervals_test.png",
    ):
        """Plot 3: Prediction Interval vs Actual Target on Test Set."""
        fig, ax = plt.subplots(figsize=(12, 5.5))

        ax.fill_between(
            test_index,
            q_lower,
            q_upper,
            color="#aec7e8",
            alpha=0.5,
            label="80% Quantile Prediction Interval [q10, q90]",
        )
        ax.plot(test_index, y_true, color="#111111", linewidth=1.6, label="Actual 72h Min DO")
        ax.plot(test_index, y_pred_ml, color="#1f77b4", linewidth=1.3, label="Point Forecast (LightGBM)")

        ax.set_xlabel("Prediction Timestamp (UTC)")
        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title(f"Uncertainty Quantification: 80% Prediction Interval on Test Set (Empirical Coverage: {empirical_coverage:.1f}%)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))

        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_4_residual_distribution(
        self,
        residuals: np.ndarray,
        filename: str = "4_residual_distribution.png",
    ):
        """Plot 4: Residual Distribution (Histogram and Statistics)."""
        fig, ax = plt.subplots(figsize=(8, 5))

        counts, bins, _ = ax.hist(residuals, bins=40, density=True, color="#4a7bb0", edgecolor="white", alpha=0.75, label="Residuals (Pred - Actual)")

        # Normal density overlay for comparison
        mu, std = float(np.mean(residuals)), float(np.std(residuals))
        x = np.linspace(bins[0], bins[-1], 200)
        p = (1.0 / (np.sqrt(2 * np.pi) * std)) * np.exp(-0.5 * ((x - mu) / std) ** 2)
        ax.plot(x, p, color="#d62728", linestyle="-", linewidth=1.8, label=f"Normal Fit (μ={mu:.2f}, σ={std:.2f})")

        ax.axvline(0.0, color="#333333", linestyle="--", linewidth=1.2, label="Zero Error Reference")

        ax.set_xlabel("Residual Error (Predicted - Actual, mg/L)")
        ax.set_ylabel("Probability Density")
        ax.set_title("Model Residual Distribution (Test Period)")

        # Percentiles box
        p10, p50, p90 = np.percentile(residuals, [10, 50, 90])
        textstr = f"Mean: {mu:.2f} mg/L\nStd: {std:.2f} mg/L\nP10: {p10:.2f} mg/L\nP50 (Median): {p50:.2f} mg/L\nP90: {p90:.2f} mg/L"
        props = dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.85, edgecolor="#cccccc")
        ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10, verticalalignment="top", bbox=props)

        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_5_residuals_vs_predicted(
        self,
        y_pred: np.ndarray,
        residuals: np.ndarray,
        filename: str = "5_residuals_vs_predicted.png",
    ):
        """Plot 5: Residuals vs Predicted Value (Heteroscedasticity Inspection)."""
        fig, ax = plt.subplots(figsize=(8, 5))

        ax.scatter(y_pred, residuals, color="#2b5c8f", alpha=0.5, edgecolors="none", s=25)
        ax.axhline(0.0, color="#d62728", linestyle="--", linewidth=1.5, label="Zero Error Line")

        # Moving average trend of residuals
        sort_idx = np.argsort(y_pred)
        x_sorted = y_pred[sort_idx]
        r_sorted = residuals[sort_idx]
        window = max(20, len(x_sorted) // 15)
        rolling_mean = pd.Series(r_sorted).rolling(window, center=True).mean()
        ax.plot(x_sorted, rolling_mean, color="#ff7f0e", linewidth=2.0, label="Local Mean Residual Trend")

        ax.set_xlabel("Predicted 72-Hour Minimum Dissolved Oxygen (mg/L)")
        ax.set_ylabel("Residual Error (Predicted - Actual, mg/L)")
        ax.set_title("Residuals vs. Predicted Values (Diagnostic for Systematic Bias)")

        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_6_baseline_vs_ml_comparison(
        self,
        comparison_df: pd.DataFrame,
        filename: str = "6_baseline_vs_ml_comparison.png",
    ):
        """Plot 6: Baseline vs ML Performance Comparison Bar Chart."""
        fig, ax = plt.subplots(figsize=(9, 5))

        models = comparison_df["MODEL"].tolist()
        maes = comparison_df["MAE (mg/L)"].astype(float).tolist()
        rmses = comparison_df["RMSE (mg/L)"].astype(float).tolist()

        x = np.arange(len(models))
        width = 0.35

        rects1 = ax.bar(x - width / 2, maes, width, label="MAE (mg/L)", color="#1f77b4")
        rects2 = ax.bar(x + width / 2, rmses, width, label="RMSE (mg/L)", color="#ff7f0e")

        ax.set_ylabel("Error Metric (mg/L)")
        ax.set_title("Forecast Accuracy Comparison: Baselines vs. LightGBM (Test Period)")
        ax.set_xticks(x)
        ax.set_xticklabels(models, rotation=15, ha="right")
        ax.legend()

        # Add data values on top of bars
        for rect in rects1:
            h = rect.get_height()
            ax.annotate(f"{h:.2f}", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9)
        for rect in rects2:
            h = rect.get_height()
            ax.annotate(f"{h:.2f}", xy=(rect.get_x() + rect.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_7_feature_importance(
        self,
        importance_df: pd.DataFrame,
        top_n: int = 15,
        filename: str = "7_feature_importance.png",
    ):
        """Plot 7: Top Features by Model Feature Importance (Statistical Gain)."""
        fig, ax = plt.subplots(figsize=(10, 6))

        top_df = importance_df.head(top_n).sort_values(by="importance_gain_pct", ascending=True)

        bars = ax.barh(top_df["feature"], top_df["importance_gain_pct"], color="#2ca02c", alpha=0.85)

        ax.set_xlabel("Model Feature Importance (% Total Relative Gain)")
        ax.set_title(f"Top {top_n} Features by Model Importance (Statistical Association, NOT Causal)")

        for bar in bars:
            w = bar.get_width()
            ax.annotate(f"{w:.1f}%", xy=(w, bar.get_y() + bar.get_height() / 2), xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_8_disturbance_backtesting_errors(
        self,
        backtest_df: pd.DataFrame,
        filename: str = "8_disturbance_backtesting_errors.png",
    ):
        """Plot 8: Historical Disturbance-Event Predictions (Actual vs Predicted)."""
        fig, ax = plt.subplots(figsize=(11, 5.5))

        events = backtest_df.copy()
        events["event_label"] = [f"Ev {row['event_id']}\n({row['partition'][:4]})" for _, row in events.iterrows()]

        x = np.arange(len(events))
        width = 0.35

        ax.bar(x - width / 2, events["actual_min_do_72h"], width, label="Actual Observed Min DO (mg/L)", color="#333333", alpha=0.85)
        ax.bar(x + width / 2, events["pred_ml"], width, label="Pre-Event ML Prediction (mg/L)", color="#1f77b4", alpha=0.85)

        # Plot quantile intervals as error bars if available
        if "quantile_10" in events.columns and "quantile_90" in events.columns:
            yerr_lower = np.maximum(0, events["pred_ml"] - events["quantile_10"].fillna(events["pred_ml"]))
            yerr_upper = np.maximum(0, events["quantile_90"].fillna(events["pred_ml"]) - events["pred_ml"])
            ax.errorbar(
                x + width / 2,
                events["pred_ml"],
                yerr=[yerr_lower, yerr_upper],
                fmt="none",
                ecolor="#d62728",
                capsize=3,
                label="Pre-Event 80% Quantile Interval",
            )

        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title("Pre-Event 72-Hour Minimum DO Predictions Across Candidate Storm Disturbance Events")
        ax.set_xticks(x)
        ax.set_xticklabels(events["event_label"], fontsize=8)
        ax.legend(loc="upper right", framealpha=0.9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_9_interval_coverage_reliability(
        self,
        nominal_coverages: List[float],
        observed_coverages: List[float],
        method_name: str = "Quantile LightGBM",
        filename: str = "9_interval_coverage_reliability.png",
    ):
        """Plot 9: Prediction Coverage / Reliability Diagram."""
        fig, ax = plt.subplots(figsize=(6.5, 6))

        nom_pct = [c * 100.0 for c in nominal_coverages]
        obs_pct = observed_coverages

        ax.plot([0, 100], [0, 100], color="#d62728", linestyle="--", linewidth=1.5, label="Perfect Reliability (Nominal = Observed)")
        ax.plot(nom_pct, obs_pct, marker="o", color="#1f77b4", linewidth=2.0, markersize=8, label=f"Observed Coverage ({method_name})")

        for x, y in zip(nom_pct, obs_pct):
            ax.annotate(f"{y:.1f}%", xy=(x, y), xytext=(-10, 10), textcoords="offset points", fontsize=9, fontweight="bold")

        ax.set_xlim(50, 100)
        ax.set_ylim(50, 100)
        ax.set_xlabel("Nominal Target Coverage (%)")
        ax.set_ylabel("Observed Empirical Coverage on Test Set (%)")
        ax.set_title(f"Uncertainty Calibration: Nominal vs. Observed Coverage ({method_name})")
        ax.legend(loc="lower right")

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)
