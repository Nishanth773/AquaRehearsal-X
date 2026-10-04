"""
AquaRehearsal-X - Exploratory Environmental Data Visualization
Stage 1: Real Data Foundation

Generates publication-quality scientific plots strictly from real sensor data:
1. Dissolved oxygen over time
2. Water temperature over time
3. Discharge over time
4. Turbidity over time (if available)
5. DO vs temperature
6. DO vs discharge
7. DO vs turbidity (if available)
8. Missing-data timeline
9. Variable availability timeline

Scientific Integrity:
- Only generates a plot if the variable exists and contains valid observations.
- Never fabricates points or interpolations for visual completeness.
"""

from pathlib import Path
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config.settings import PLOTS_DIR
from src.utils.logger import logger


class ExploratoryPlotter:
    """Produces scientific exploratory visualizations for validated station datasets."""

    def __init__(self, output_dir: Path = PLOTS_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Scientific plot styling
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        plt.rcParams.update({
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.titlesize": 13,
            "figure.dpi": 150,
        })

    def generate_all_plots(self, df: pd.DataFrame, station_id: str, station_name: str) -> List[Path]:
        """Runs the complete suite of real-data visualizations for a station."""
        generated: List[Path] = []
        if df.empty:
            logger.warning("Cannot generate plots for empty DataFrame.")
            return generated

        logger.info("Generating exploratory plots for station %s (%s)...", station_id, station_name)

        # 1. Dissolved Oxygen Time Series
        if "dissolved_oxygen" in df.columns and df["dissolved_oxygen"].notna().sum() > 0:
            p = self.plot_do_over_time(df, station_id, station_name)
            if p: generated.append(p)

        # 2. Water Temperature Time Series
        if "water_temperature" in df.columns and df["water_temperature"].notna().sum() > 0:
            p = self.plot_temperature_over_time(df, station_id, station_name)
            if p: generated.append(p)

        # 3. Discharge Time Series
        if "discharge" in df.columns and df["discharge"].notna().sum() > 0:
            p = self.plot_discharge_over_time(df, station_id, station_name)
            if p: generated.append(p)

        # 4. Turbidity Time Series
        if "turbidity" in df.columns and df["turbidity"].notna().sum() > 0:
            p = self.plot_turbidity_over_time(df, station_id, station_name)
            if p: generated.append(p)

        # 5. DO vs Temperature Scatter
        if "dissolved_oxygen" in df.columns and "water_temperature" in df.columns:
            valid_both = df[["dissolved_oxygen", "water_temperature"]].dropna()
            if len(valid_both) > 10:
                p = self.plot_do_vs_temperature(valid_both, station_id, station_name)
                if p: generated.append(p)

        # 6. DO vs Discharge Scatter
        if "dissolved_oxygen" in df.columns and "discharge" in df.columns:
            valid_both = df[["dissolved_oxygen", "discharge"]].dropna()
            if len(valid_both) > 10:
                p = self.plot_do_vs_discharge(valid_both, station_id, station_name)
                if p: generated.append(p)

        # 7. DO vs Turbidity Scatter
        if "dissolved_oxygen" in df.columns and "turbidity" in df.columns:
            valid_both = df[["dissolved_oxygen", "turbidity"]].dropna()
            if len(valid_both) > 10:
                p = self.plot_do_vs_turbidity(valid_both, station_id, station_name)
                if p: generated.append(p)

        # 8. Missing Data Timeline
        p = self.plot_missing_data_timeline(df, station_id, station_name)
        if p: generated.append(p)

        # 9. Variable Availability Timeline
        p = self.plot_variable_availability_timeline(df, station_id, station_name)
        if p: generated.append(p)

        logger.info("Successfully generated %d plots in %s", len(generated), self.output_dir)
        return generated

    def plot_do_over_time(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(12, 5))
        series = df["dissolved_oxygen"].dropna()
        ax.plot(series.index, series.values, color="#0077b6", linewidth=0.8, alpha=0.85, label="Observed DO (mg/L)")
        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title(f"Real Dissolved Oxygen Time Series — Station {station_id}\n{station_name}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        ax.legend(loc="upper right")
        out_path = self.output_dir / f"{station_id}_1_do_timeseries.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_temperature_over_time(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(12, 5))
        series = df["water_temperature"].dropna()
        ax.plot(series.index, series.values, color="#d90429", linewidth=0.8, alpha=0.85, label="Water Temp (°C)")
        ax.set_ylabel("Water Temperature (°C)")
        ax.set_title(f"Real Water Temperature Time Series — Station {station_id}\n{station_name}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        ax.legend(loc="upper right")
        out_path = self.output_dir / f"{station_id}_2_temperature_timeseries.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_discharge_over_time(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(12, 5))
        series = df["discharge"].dropna()
        ax.plot(series.index, series.values, color="#2b2d42", linewidth=0.9, alpha=0.9, label="Stream Discharge (cfs)")
        ax.set_ylabel("Discharge (cfs)")
        ax.set_yscale("log")
        ax.set_title(f"Real Stream Discharge Time Series (Log Scale) — Station {station_id}\n{station_name}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        ax.legend(loc="upper right")
        out_path = self.output_dir / f"{station_id}_3_discharge_timeseries.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_turbidity_over_time(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(12, 5))
        series = df["turbidity"].dropna()
        ax.plot(series.index, series.values, color="#7f4f24", linewidth=0.8, alpha=0.85, label="Turbidity (FNU/NTU)")
        ax.set_ylabel("Turbidity (FNU/NTU)")
        ax.set_title(f"Real Turbidity Time Series — Station {station_id}\n{station_name}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        ax.legend(loc="upper right")
        out_path = self.output_dir / f"{station_id}_4_turbidity_timeseries.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_do_vs_temperature(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(df["water_temperature"], df["dissolved_oxygen"], color="#0077b6", alpha=0.3, s=12, edgecolors="none")
        ax.set_xlabel("Water Temperature (°C)")
        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title(f"Dissolved Oxygen vs. Water Temperature — Station {station_id}\n{station_name}")
        out_path = self.output_dir / f"{station_id}_5_do_vs_temperature.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_do_vs_discharge(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(df["discharge"], df["dissolved_oxygen"], color="#40916c", alpha=0.3, s=12, edgecolors="none")
        ax.set_xscale("log")
        ax.set_xlabel("Stream Discharge (cfs, Log Scale)")
        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title(f"Dissolved Oxygen vs. Stream Discharge — Station {station_id}\n{station_name}")
        out_path = self.output_dir / f"{station_id}_6_do_vs_discharge.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_do_vs_turbidity(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(df["turbidity"], df["dissolved_oxygen"], color="#b08968", alpha=0.35, s=12, edgecolors="none")
        ax.set_xscale("log")
        ax.set_xlabel("Turbidity (FNU/NTU, Log Scale)")
        ax.set_ylabel("Dissolved Oxygen (mg/L)")
        ax.set_title(f"Dissolved Oxygen vs. Turbidity — Station {station_id}\n{station_name}")
        out_path = self.output_dir / f"{station_id}_7_do_vs_turbidity.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_missing_data_timeline(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(12, 4))
        target_vars = [c for c in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"] if c in df.columns]
        if not target_vars:
            plt.close(fig)
            return None

        # Sample or resample to daily presence indicator
        daily_presence = df[target_vars].notna().astype(int).resample("1D").max()

        y_positions = list(range(len(target_vars)))
        for idx, var in enumerate(target_vars):
            present_dates = daily_presence.index[daily_presence[var] == 1]
            ax.scatter(present_dates, [idx] * len(present_dates), marker="|", s=40, color="#1b4965")

        ax.set_yticks(y_positions)
        ax.set_yticklabels(target_vars)
        ax.set_title(f"Daily Sensor Presence Timeline — Station {station_id}\n{station_name}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        out_path = self.output_dir / f"{station_id}_8_missing_data_timeline.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path

    def plot_variable_availability_timeline(self, df: pd.DataFrame, station_id: str, station_name: str) -> Optional[Path]:
        fig, ax = plt.subplots(figsize=(12, 5))
        target_vars = [c for c in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"] if c in df.columns]
        if not target_vars:
            plt.close(fig)
            return None

        # Calculate weekly availability percentages
        weekly_pct = df[target_vars].notna().astype(float).resample("1W").mean() * 100.0

        colors = {"dissolved_oxygen": "#0077b6", "water_temperature": "#d90429", "discharge": "#2b2d42", "turbidity": "#7f4f24"}
        for var in target_vars:
            ax.plot(weekly_pct.index, weekly_pct[var], label=f"{var} (%)", color=colors.get(var, "#6c757d"), linewidth=1.2)

        ax.set_ylabel("Weekly Data Completeness (%)")
        ax.set_ylim(-5, 105)
        ax.set_title(f"Weekly Parameter Availability (%) — Station {station_id}\n{station_name}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        ax.legend(loc="lower left")
        out_path = self.output_dir / f"{station_id}_9_variable_availability_timeline.png"
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)
        return out_path
