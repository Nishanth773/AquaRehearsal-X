"""
AquaRehearsal-X - Stage 2.5 Visualization Suite
Historical Depth + Real Precipitation Upgrade

Generates 10 publication-grade scientific figures saved under data/reports/stage2_5/:
1. Long-term DO timeline (2023-2026 multi-year record)
2. Long-term rainfall timeline
3. Rainfall vs discharge dynamics
4. Rainfall vs DO response
5. Storm event rainfall hydrographs
6. Actual vs predicted minimum DO (Model A vs Model B)
7. Model A vs Model B error comparison
8. Storm-event error comparison
9. Rainfall feature importance
10. Prediction interval behavior
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from sklearn.metrics import mean_absolute_error
from src.config.stage2_5_settings import STAGE2_5_PLOTS_DIR
from src.utils.logger import logger

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


class Stage2_5Plotter:
    """Generates all 10 scientific figures for Stage 2.5."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or STAGE2_5_PLOTS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_1_longterm_do_timeline(self, df: pd.DataFrame, filename: str = "1_longterm_do_timeline.png"):
        """Plot 1: 3.75-year continuous dissolved oxygen series showing multi-season dynamics."""
        fig, ax = plt.subplots(figsize=(14, 5.5))

        ax.plot(df.index, df["dissolved_oxygen"], color="#1f77b4", linewidth=0.8, alpha=0.85, label="Observed DO (mg/L)")
        ax.axhline(5.0, color="#d62728", linestyle="--", linewidth=1.2, label="Warm-Water Aquatic Benchmark (5.0 mg/L)")

        # 30-day rolling mean for seasonal trend
        rolling_30d = df["dissolved_oxygen"].rolling("30D", min_periods=20).mean()
        ax.plot(df.index, rolling_30d, color="#ff7f0e", linewidth=2.0, label="30-Day Seasonal Mean DO")

        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title("Multi-Year Dissolved Oxygen Dynamics (2023–2026) — USGS 01474500 (Schuylkill River)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        ax.legend(loc="upper right", framealpha=0.9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_2_longterm_rainfall_timeline(self, df: pd.DataFrame, filename: str = "2_longterm_rainfall_timeline.png"):
        """Plot 2: Long-term precipitation hyetograph and cumulative rainfall curve."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)

        # Daily rainfall aggregation for readable visualization (prioritize liquid rain_mm)
        rain_col = "rain_mm" if "rain_mm" in df.columns else "precipitation_mm"
        daily_rain = df[rain_col].resample("1D").sum()
        ax1.bar(daily_rain.index, daily_rain.values, width=1.0, color="#2b5c8f", alpha=0.8, label="Daily Liquid Rain (mm)")
        ax1.set_ylabel("Rainfall (mm/day)")
        ax1.set_title("Historical Rainfall Timeline (2023–2026) — Open-Meteo ECMWF ERA5 (40.0° N, -75.25° W)")
        ax1.legend(loc="upper left")

        # Cumulative curve
        cum_rain = df[rain_col].cumsum()
        ax2.plot(df.index, cum_rain, color="#008080", linewidth=1.8, label=f"Cumulative Rainfall (Total: {cum_rain.iloc[-1]:.0f} mm)")
        ax2.set_ylabel("Cumulative (mm)")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        ax2.legend(loc="upper left")

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_3_rainfall_vs_discharge(self, df: pd.DataFrame, filename: str = "3_rainfall_vs_discharge.png"):
        """Plot 3: Rainfall pulses vs stream discharge response (demonstrating runoff lag)."""
        # Focus on a representative 6-month period showing multiple severe storms
        sub = df.loc["2024-03-01":"2024-09-01"]
        rain_col = "rain_mm" if "rain_mm" in sub.columns else "precipitation_mm"
        fig, ax1 = plt.subplots(figsize=(13, 6))

        # Inverted precipitation hyetograph on top
        ax2 = ax1.twinx()
        daily_p = sub[rain_col].resample("1D").sum()
        ax2.bar(daily_p.index, daily_p.values, width=0.8, color="#3470a3", alpha=0.5, label="Daily Rainfall (mm)")
        ax2.set_ylabel("Rainfall (mm/day)", color="#3470a3")
        ax2.tick_params(axis="y", labelcolor="#3470a3")
        ax2.set_ylim(max(daily_p.values) * 3, 0)  # Inverted

        # Discharge hydrograph on primary axis
        ax1.plot(sub.index, sub["discharge"], color="#111111", linewidth=1.5, label="Stream Discharge (cfs)")
        ax1.set_ylabel("Stream Discharge (cfs)", color="#111111")
        ax1.set_title("Precipitation Forcing vs. Streamflow Hydrograph Response (Schuylkill River)")
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_4_rainfall_vs_do_response(self, df: pd.DataFrame, filename: str = "4_rainfall_vs_do_response.png"):
        """Plot 4: Rainfall events coupled with post-storm dissolved oxygen depressions."""
        sub = df.loc["2024-06-01":"2024-09-01"]
        rain_col = "rain_mm" if "rain_mm" in sub.columns else "precipitation_mm"
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True, gridspec_kw={"height_ratios": [1, 2]})

        # Rainfall
        hourly_p = sub[rain_col]
        ax1.bar(hourly_p.index, hourly_p.values, width=0.04, color="#1f77b4", label="Hourly Rainfall (mm)")
        ax1.set_ylabel("Rainfall (mm/h)")
        ax1.set_title("Coupled Summer Storm Precipitation and Dissolved Oxygen Response (June–August 2024)")
        ax1.legend(loc="upper right")

        # DO with ecological line
        ax2.plot(sub.index, sub["dissolved_oxygen"], color="#2ca02c", linewidth=1.2, label="Observed DO (mg/L)")
        ax2.axhline(5.0, color="#d62728", linestyle="--", linewidth=1.2, label="Hypoxia Benchmark (5.0 mg/L)")
        ax2.set_ylabel("Dissolved Oxygen (mg/L)")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax2.legend(loc="upper right")

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_5_storm_event_rainfall_hydrographs(self, df: pd.DataFrame, events_df: pd.DataFrame, filename: str = "5_storm_event_rainfall_hydrographs.png"):
        """Plot 5: Zoomed multi-panel storm event case studies."""
        # Pick 2 contrasting major events
        top_events = events_df.sort_values(by="peak_discharge_cfs", ascending=False).head(2)
        fig, axes = plt.subplots(len(top_events), 1, figsize=(12, 4.5 * len(top_events)), sharex=False)
        if len(top_events) == 1:
            axes = [axes]

        for ax, (_, ev) in zip(axes, top_events.iterrows()):
            e_start = pd.to_datetime(ev["event_start"], utc=True)
            w_start = e_start - pd.Timedelta(hours=24)
            w_end = e_start + pd.Timedelta(hours=96)
            sub = df.loc[w_start:w_end]
            rain_col = "rain_mm" if "rain_mm" in sub.columns else "precipitation_mm"

            ax_p = ax.twinx()
            ax_p.bar(sub.index, sub[rain_col], width=0.03, color="#aec7e8", alpha=0.7, label="Rainfall (mm/h)")
            ax_p.set_ylabel("Rainfall (mm/h)", color="#1f77b4")
            ax_p.set_ylim(max(sub[rain_col].fillna(0)) * 3, 0)

            ax.plot(sub.index, sub["dissolved_oxygen"], color="#2ca02c", linewidth=2.0, label="DO (mg/L)")
            ax.axvline(e_start, color="#d62728", linestyle=":", linewidth=1.5, label="Storm Surge Start")
            ax.set_ylabel("DO (mg/L)", color="#2ca02c")
            ax.set_title(f"Storm Event {ev['event_id']} ({e_start.strftime('%Y-%m-%d')} | Peak Q: {ev['peak_discharge_cfs']:.0f} cfs | Rain: {ev['cumulative_rainfall_mm']:.1f} mm)")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_6_actual_vs_predicted_min_do(
        self,
        y_true: np.ndarray,
        y_pred_a: np.ndarray,
        y_pred_b: np.ndarray,
        filename: str = "6_actual_vs_predicted_min_do.png",
    ):
        """Plot 6: Actual vs Predicted Minimum DO Scatter Plot for Model A and Model B."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6), sharey=True, sharex=True)

        min_val = min(np.nanmin(y_true), np.nanmin(y_pred_a), np.nanmin(y_pred_b)) - 0.5
        max_val = max(np.nanmax(y_true), np.nanmax(y_pred_a), np.nanmax(y_pred_b)) + 0.5

        # Model A
        ax1.scatter(y_true, y_pred_a, color="#1f77b4", alpha=0.3, s=20)
        ax1.plot([min_val, max_val], [min_val, max_val], color="#d62728", linestyle="--", linewidth=1.5)
        mae_a = mean_absolute_error(y_true, y_pred_a)
        ax1.set_title(f"Model A (Water-Only)\nMAE: {mae_a:.2f} mg/L")
        ax1.set_xlabel("Actual 72h Minimum DO (mg/L)")
        ax1.set_ylabel("Predicted 72h Minimum DO (mg/L)")
        ax1.set_xlim(min_val, max_val)
        ax1.set_ylim(min_val, max_val)

        # Model B
        ax2.scatter(y_true, y_pred_b, color="#2ca02c", alpha=0.3, s=20)
        ax2.plot([min_val, max_val], [min_val, max_val], color="#d62728", linestyle="--", linewidth=1.5)
        mae_b = mean_absolute_error(y_true, y_pred_b)
        ax2.set_title(f"Model B (Water + Precipitation)\nMAE: {mae_b:.2f} mg/L")
        ax2.set_xlabel("Actual 72h Minimum DO (mg/L)")
        ax2.set_xlim(min_val, max_val)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_7_model_a_vs_model_b_comparison(self, comp_df: pd.DataFrame, filename: str = "7_model_a_vs_model_b_comparison.png"):
        """Plot 7: Grouped Bar Chart comparing Model A vs Model B across regimes."""
        fig, ax = plt.subplots(figsize=(10, 5.5))

        regimes = comp_df["EVALUATION REGIME"].unique()
        x = np.arange(len(regimes))
        width = 0.35

        maes_a = [comp_df[(comp_df["EVALUATION REGIME"] == r) & (comp_df["MODEL"] == "Model A (Water-Only)")]["MAE (mg/L)"].values[0] for r in regimes]
        maes_b = [comp_df[(comp_df["EVALUATION REGIME"] == r) & (comp_df["MODEL"] == "Model B (Water + Precipitation)")]["MAE (mg/L)"].values[0] for r in regimes]

        rects1 = ax.bar(x - width / 2, maes_a, width, label="Model A (Water-Only)", color="#1f77b4")
        rects2 = ax.bar(x + width / 2, maes_b, width, label="Model B (Water + Precipitation)", color="#2ca02c")

        ax.set_ylabel("Mean Absolute Error (mg/L)")
        ax.set_title("Forecast Accuracy Comparison: Model A vs. Model B (Unseen Test Set)")
        ax.set_xticks(x)
        ax.set_xticklabels([r.replace(" Only", "") for r in regimes], rotation=10, ha="right")
        ax.legend()

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

    def plot_8_storm_event_error_comparison(self, storm_comp_df: pd.DataFrame, filename: str = "8_storm_event_error_comparison.png"):
        """Plot 8: Storm-Event Backtesting Absolute Error Comparison (Model A vs Model B)."""
        fig, ax = plt.subplots(figsize=(10, 5))

        events = storm_comp_df.copy()
        x = np.arange(len(events))
        width = 0.35

        ax.bar(x - width / 2, events["model_a_abs_error"], width, label="Model A (Water-Only) Abs Error", color="#1f77b4")
        ax.bar(x + width / 2, events["model_b_abs_error"], width, label="Model B (Water + Precip) Abs Error", color="#2ca02c")

        ax.set_ylabel("Absolute Prediction Error (mg/L)")
        ax.set_title("Pre-Event 72h Min DO Forecast Errors on Test Storm Events")
        ax.set_xticks(x)
        ax.set_xticklabels([f"Ev {row['event_id']}\n({row['event_start'][5:10]})" for _, row in events.iterrows()])
        ax.legend()

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_9_rainfall_feature_importance(self, imp_df: pd.DataFrame, filename: str = "9_rainfall_feature_importance.png"):
        """Plot 9: Top features by model importance with rainfall features highlighted."""
        fig, ax = plt.subplots(figsize=(10, 6.5))

        top_df = imp_df.head(15).sort_values(by="importance_gain_pct", ascending=True)

        colors = ["#ff7f0e" if ("rainfall" in f or "surge" in f) else "#2ca02c" for f in top_df["feature"]]
        bars = ax.barh(top_df["feature"], top_df["importance_gain_pct"], color=colors, alpha=0.85)

        ax.set_xlabel("Model Feature Importance (% Total Relative Gain)")
        ax.set_title("Model B Top 15 Feature Importances (Orange = Precipitation/Storm Dynamics)")

        for bar in bars:
            w = bar.get_width()
            ax.annotate(f"{w:.1f}%", xy=(w, bar.get_y() + bar.get_height() / 2), xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)

    def plot_10_prediction_interval_behavior(
        self,
        test_index: pd.DatetimeIndex,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        q_lower: np.ndarray,
        q_upper: np.ndarray,
        filename: str = "10_prediction_interval_behavior.png",
    ):
        """Plot 10: Multi-month prediction intervals over unseen test period."""
        fig, ax = plt.subplots(figsize=(13, 5.5))

        ax.fill_between(test_index, q_lower, q_upper, color="#aec7e8", alpha=0.5, label="80% Quantile Prediction Interval [q10, q90]")
        ax.plot(test_index, y_true, color="#111111", linewidth=1.5, label="Actual 72h Min DO Ground Truth")
        ax.plot(test_index, y_pred, color="#2ca02c", linewidth=1.2, label="Model B Point Prediction")

        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title("Model B 80% Prediction Interval Trajectory Across Unseen 2026 Test Season")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.legend(loc="upper right", framealpha=0.9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        logger.info("Saved %s", out_path)
