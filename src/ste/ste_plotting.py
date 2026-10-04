"""
AquaRehearsal-X - Stage 3 Visualization Suite
Storm Tolerance Envelope (STE), Dynamic Conditioning & Early-Warning Figures

Generates 8 publication-grade scientific figures saved under data/reports/stage3/:
1. 1_storm_tolerance_envelope_2d.png: 2D phase space (Rain vs Surge) with safe/hazard zones and historical storms.
2. 2_thermal_conditioning_envelopes.png: Dynamic envelope shrinkage across thermal regimes.
3. 3_antecedent_wetness_shift.png: Critical rainfall threshold shift vs antecedent moisture.
4. 4_boundary_crossing_probability_curves.png: Probability risk curves across temperatures.
5. 5_time_to_trough_distribution.png: Action window latency dynamics and urgency tiers.
6. 6_historical_event_envelope_backtest.png: Event-by-event backtest scatter and contingency matrix.
7. 7_action_window_chronology_case_study.png: June 2026 acute hypoxia event operational timeline.
8. 8_early_warning_reliability_diagram.png: Empirical calibration reliability diagram for P_cross.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

from src.config.stage3_settings import (
    STAGE3_PLOTS_DIR,
    STAGE3_REGULATORY_THRESHOLDS,
    EARLY_WARNING_LEVELS,
    ACTION_WINDOW_TIERS,
)
from src.ste.envelope_engine import StormToleranceEnvelope, calculate_benson_krause_saturation
from src.ste.probability_engine import BoundaryCrossingProbability
from src.ste.action_window import ActionWindowEstimator
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


class Stage3Plotter:
    """Generates all 8 publication-grade scientific figures for Stage 3."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or STAGE3_PLOTS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ste_engine = StormToleranceEnvelope()
        self.prob_engine = BoundaryCrossingProbability()
        self.window_estimator = ActionWindowEstimator()

    def plot_1_storm_tolerance_envelope_2d(
        self,
        df_events: pd.DataFrame,
        filename: str = "1_storm_tolerance_envelope_2d.png",
    ):
        """Plot 1: 2D phase space with tolerance zones and historical event scatter."""
        fig, ax = plt.subplots(figsize=(11, 7.5))

        # Generate grid for moderate summer conditions (T=22°C, DO=7.5 mg/L, Q=1200 cfs)
        R_mesh, S_mesh, DO_mesh = self.ste_engine.generate_2d_envelope_grid(
            ambient_temp_c=22.0,
            ambient_do_mg_L=7.5,
            ambient_discharge_cfs=1200.0,
            antecedent_rain_72h_mm=10.0,
            rain_steps=80,
            surge_steps=80,
        )

        # Filled contour zones
        levels = [0.0, 2.0, 4.0, 5.0, 15.0]
        colors = ["#e0b2e6", "#fbcbc9", "#fee9b2", "#c8e6c9"]  # Hypoxia, Warning, Advisory, Safe
        cs = ax.contourf(R_mesh, S_mesh, DO_mesh, levels=levels, colors=colors, alpha=0.85)

        # Boundary contour lines
        c_lines = ax.contour(R_mesh, S_mesh, DO_mesh, levels=[2.0, 4.0, 5.0], colors=["#7b1fa2", "#d62728", "#2ca02c"], linewidths=2.0)
        ax.clabel(c_lines, inline=True, fmt={2.0: "2.0 mg/L (Hypoxia)", 4.0: "4.0 mg/L (Acute)", 5.0: "5.0 mg/L (Std)"}, fontsize=10)

        # Overlay historical storm events
        breached = df_events["observed_min_do_72h"] < 5.0
        ax.scatter(
            df_events.loc[~breached, "storm_rain_mm"],
            df_events.loc[~breached, "surge_ratio"],
            color="#1b5e20", edgecolor="white", s=65, label="Historical Storms (DO >= 5.0 mg/L Compliant)", zorder=4
        )
        ax.scatter(
            df_events.loc[breached, "storm_rain_mm"],
            df_events.loc[breached, "surge_ratio"],
            color="#b71c1c", edgecolor="black", s=85, marker="^", label="Historical Storms (DO < 5.0 mg/L Depleted)", zorder=5
        )

        ax.set_xlabel("Incoming Storm Rainfall Depth (mm)")
        ax.set_ylabel("Discharge Surge Ratio (Q_peak / Q_base)")
        ax.set_title("AquaRehearsal-X — 2D Storm Tolerance Envelope (USGS 01474500, T=22°C)\nResilience Boundaries Across Hydrologic-Meteorological Perturbations")
        ax.set_xlim(0, 75)
        ax.set_ylim(1, 14)

        # Custom Legend
        legend_elements = [
            Patch(facecolor="#c8e6c9", edgecolor="#2ca02c", label="SAFE ZONE: DO >= 5.0 mg/L"),
            Patch(facecolor="#fee9b2", edgecolor="#ff7f0e", label="ADVISORY ZONE: 4.0 <= DO < 5.0 mg/L"),
            Patch(facecolor="#fbcbc9", edgecolor="#d62728", label="WARNING ZONE: 2.0 <= DO < 4.0 mg/L"),
            Patch(facecolor="#e0b2e6", edgecolor="#7b1fa2", label="EMERGENCY ZONE: DO < 2.0 mg/L (Hypoxia)"),
        ]
        ax.legend(handles=legend_elements + list(ax.get_legend_handles_labels()[0]), loc="upper right", framealpha=0.92)

        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 1 to %s", save_path)

    def plot_2_thermal_conditioning_envelopes(self, filename: str = "2_thermal_conditioning_envelopes.png"):
        """Plot 2: Thermal contraction of tolerance envelopes across regimes."""
        fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), sharey=True)

        thermal_scenarios = [
            ("Cold Water Regime (T = 10°C)", 10.0, 11.0, axes[0]),
            ("Moderate Water Regime (T = 18°C)", 18.0, 8.8, axes[1]),
            ("Warm Summer Regime (T = 25°C)", 25.0, 7.2, axes[2]),
        ]

        levels = [0.0, 2.0, 4.0, 5.0, 15.0]
        colors = ["#e0b2e6", "#fbcbc9", "#fee9b2", "#c8e6c9"]

        for title, temp, base_do, ax in thermal_scenarios:
            R_mesh, S_mesh, DO_mesh = self.ste_engine.generate_2d_envelope_grid(
                ambient_temp_c=temp,
                ambient_do_mg_L=base_do,
                ambient_discharge_cfs=1200.0,
                antecedent_rain_72h_mm=10.0,
            )
            ax.contourf(R_mesh, S_mesh, DO_mesh, levels=levels, colors=colors, alpha=0.85)
            c_lines = ax.contour(R_mesh, S_mesh, DO_mesh, levels=[2.0, 4.0, 5.0], colors=["#7b1fa2", "#d62728", "#2ca02c"], linewidths=1.8)
            ax.clabel(c_lines, inline=True, fmt={2.0: "2.0", 4.0: "4.0", 5.0: "5.0"}, fontsize=9)
            ax.set_title(title, fontweight="bold")
            ax.set_xlabel("Storm Rainfall (mm)")
            ax.set_xlim(0, 75)
            ax.set_ylim(1, 14)

        axes[0].set_ylabel("Discharge Surge Ratio (Q_peak / Q_base)")
        fig.suptitle("Thermal Contraction of the Storm Tolerance Envelope: DO Assimilative Space Shrinkage with Temperature", fontsize=14, y=1.02)
        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 2 to %s", save_path)

    def plot_3_antecedent_wetness_shift(self, filename: str = "3_antecedent_wetness_shift.png"):
        """Plot 3: Critical rainfall threshold shift vs antecedent moisture and temperature."""
        fig, ax = plt.subplots(figsize=(10, 6))

        temps = np.linspace(6.0, 28.0, 45)
        api_scenarios = [
            ("Dry Catchment (API < 5 mm)", 2.0, "#2ca02c", "-"),
            ("Normal Catchment (API = 12 mm)", 12.0, "#ff7f0e", "--"),
            ("Saturated Catchment (API >= 30 mm)", 35.0, "#d62728", "-."),
        ]

        for label, api_val, color, style in api_scenarios:
            r_crits = []
            for t in temps:
                do_base = min(11.5, calculate_benson_krause_saturation(t) * 0.92)
                r_c = self.ste_engine.compute_critical_rainfall(
                    ambient_temp_c=t,
                    ambient_do_mg_L=do_base,
                    ambient_discharge_cfs=1200.0,
                    discharge_surge_ratio=3.5,
                    antecedent_rain_72h_mm=api_val,
                    target_threshold=4.0,
                )
                r_crits.append(r_c)
            ax.plot(temps, r_crits, label=label, color=color, linestyle=style, linewidth=2.4)

        ax.axvspan(22.0, 28.0, color="#ffebee", alpha=0.4, label="Critical Warm Summer Window (>=22°C)")
        ax.set_xlabel("Ambient Water Temperature (°C)")
        ax.set_ylabel("Critical Rainfall Depth to Breach 4.0 mg/L (mm)")
        ax.set_title("Dynamic Shrinkage of Critical Storm Rainfall Capacity (R_crit)\nConditioned on Ambient Water Temperature and 72h Antecedent Catchment Moisture")
        ax.set_ylim(0, 85)
        ax.legend(loc="upper right", framealpha=0.92)

        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 3 to %s", save_path)

    def plot_4_boundary_crossing_probability_curves(self, filename: str = "4_boundary_crossing_probability_curves.png"):
        """Plot 4: Risk curves of P(DO < 4.0 mg/L) across temperatures."""
        fig, ax = plt.subplots(figsize=(10, 6))

        rains = np.linspace(0.0, 65.0, 65)
        temp_profiles = [
            ("Cold (10°C)", 10.0, 11.2, "#1f77b4"),
            ("Moderate Spring (18°C)", 18.0, 8.8, "#ff7f0e"),
            ("Warm Summer (24°C)", 24.0, 7.4, "#d62728"),
            ("Severe Summer Heatwave (28°C)", 28.0, 6.5, "#7b1fa2"),
        ]

        for label, t, do_base, col in temp_profiles:
            p_cross_acute = []
            for r in rains:
                est_do = self.ste_engine.estimate_minimum_do(
                    ambient_temp_c=t,
                    ambient_do_mg_L=do_base,
                    ambient_discharge_cfs=1200.0,
                    storm_rain_mm=r,
                    discharge_surge_ratio=3.0,
                    antecedent_rain_72h_mm=10.0,
                )
                probs = self.prob_engine.compute_crossing_probabilities(expected_min_do=est_do, ambient_temp_c=t)
                p_cross_acute.append(probs["p_crossing_acute_4_0"])
            ax.plot(rains, p_cross_acute, label=label, color=col, linewidth=2.2)

        # Operational alert threshold lines
        ax.axhline(0.10, color="#ff7f0e", linestyle=":", linewidth=1.5, label="Advisory Trigger (P >= 0.10)")
        ax.axhline(0.35, color="#d62728", linestyle="--", linewidth=1.5, label="Warning Trigger (P >= 0.35)")
        ax.axhline(0.70, color="#7b1fa2", linestyle="-.", linewidth=1.5, label="Emergency Trigger (P >= 0.70)")

        ax.set_xlabel("Incoming Storm Rainfall Depth (mm)")
        ax.set_ylabel("Probability of Acute Standard Breach: P(DO_min < 4.0 mg/L)")
        ax.set_title("Boundary-Crossing Probability Risk Curves (USGS 01474500)\nNonlinear Ecological Fragility Conditioned on Thermal Energy")
        ax.set_ylim(-0.02, 1.02)
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), framealpha=0.92)

        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 4 to %s", save_path)

    def plot_5_time_to_trough_distribution(
        self,
        df_events: pd.DataFrame,
        filename: str = "5_time_to_trough_distribution.png",
    ):
        """Plot 5: Action window latency dynamics across historical events."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        valid_lags = df_events.dropna(subset=["observed_time_to_trough_h"])

        # Histogram of observed lags
        ax1.hist(valid_lags["observed_time_to_trough_h"], bins=14, color="#1976d2", edgecolor="black", alpha=0.75)
        ax1.axvline(valid_lags["observed_time_to_trough_h"].median(), color="#d62728", linestyle="--", linewidth=2.0, label=f"Median Lag: {valid_lags['observed_time_to_trough_h'].median():.1f}h")
        ax1.axvline(12.0, color="#ff7f0e", linestyle=":", linewidth=1.5, label="Immediate Window (<12h)")
        ax1.axvline(24.0, color="#2ca02c", linestyle="-.", linewidth=1.5, label="Standard Window (12-24h)")
        ax1.set_xlabel("Observed Hours to DO Nadir (t_trough)")
        ax1.set_ylabel("Number of Historical Disturbance Events")
        ax1.set_title("Empirical Distribution of Time-to-Trough")
        ax1.legend(loc="upper right")

        # Scatter of predicted vs observed
        ax2.scatter(valid_lags["observed_time_to_trough_h"], valid_lags["predicted_time_to_trough_h"], color="#388e3c", edgecolor="black", s=60, alpha=0.85)
        max_v = max(valid_lags["observed_time_to_trough_h"].max(), valid_lags["predicted_time_to_trough_h"].max()) + 5
        ax2.plot([0, max_v], [0, max_v], color="gray", linestyle="--", label="1:1 Identity")
        ax2.set_xlabel("Observed Time-to-Trough (hours)")
        ax2.set_ylabel("Predicted Time-to-Trough (hours)")
        ax2.set_title("Action Window Model Accuracy")
        ax2.set_xlim(0, max_v)
        ax2.set_ylim(0, max_v)
        ax2.legend(loc="upper left")

        fig.suptitle("Operational Action Window & Time-to-Trough Dynamics (58 Multi-Year Events)", fontsize=14, y=1.02)
        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 5 to %s", save_path)

    def plot_6_historical_event_envelope_backtest(
        self,
        df_events: pd.DataFrame,
        summary_metrics: Dict[str, Any],
        filename: str = "6_historical_event_envelope_backtest.png",
    ):
        """Plot 6: Scatter of actual vs predicted minimum DO and contingency breakdown."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Scatter actual vs predicted
        ax1.scatter(df_events["observed_min_do_72h"], df_events["predicted_min_do_72h"], color="#0288d1", edgecolor="black", s=65, alpha=0.85)
        ax1.plot([2, 14], [2, 14], color="gray", linestyle="--", label="1:1 Perfect Forecast")
        ax1.axhline(5.0, color="#d62728", linestyle=":", label="PA DEP Standard (5.0 mg/L)")
        ax1.axvline(5.0, color="#d62728", linestyle=":")
        ax1.axhline(4.0, color="#7b1fa2", linestyle="--", label="Acute Stress (4.0 mg/L)")
        ax1.axvline(4.0, color="#7b1fa2", linestyle="--")

        ax1.set_xlabel("Observed 72h Minimum DO (mg/L)")
        ax1.set_ylabel("STE Predicted Minimum DO (mg/L)")
        ax1.set_title("Actual vs Predicted Minimum DO Across 58 Storms")
        ax1.legend(loc="upper left")

        # Contingency Matrix visualization for Deoxygenation Stress
        tp = summary_metrics.get("stress_tp", summary_metrics["true_positives_std"])
        fp = summary_metrics.get("stress_fp", summary_metrics["false_positives_std"])
        fn = summary_metrics.get("stress_fn", summary_metrics["false_negatives_std"])
        tn = summary_metrics.get("stress_tn", summary_metrics["true_negatives_std"])

        matrix = np.array([[tp, fp], [fn, tn]])
        cax = ax2.matshow(matrix, cmap="Blues", alpha=0.7)
        for i in range(2):
            for j in range(2):
                ax2.text(j, i, str(matrix[i, j]), va="center", ha="center", fontsize=18, fontweight="bold")

        ax2.set_xticks([0, 1])
        ax2.set_yticks([0, 1])
        ax2.set_xticklabels(["Warning / Advisory", "Normal / Safe"])
        ax2.set_yticklabels(["Observed Stress\n(Drop >= 1.0 mg/L)", "Observed Resilient\n(DO Compliant)"])
        sens = summary_metrics.get("stress_sensitivity", summary_metrics["sensitivity_recall"])
        spec = summary_metrics.get("stress_specificity", summary_metrics["specificity"])
        prec = summary_metrics.get("stress_precision", summary_metrics["precision"])
        f1_val = summary_metrics.get("stress_f1_score", summary_metrics["f1_score"])
        ax2.set_title(
            f"Early Warning Contingency Matrix (Storm DO Depletion Stress)\n"
            f"Sens: {sens:.2f} | Spec: {spec:.2f} | Prec: {prec:.2f} | F1: {f1_val:.2f}",
            pad=20
        )

        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 6 to %s", save_path)

    def plot_7_action_window_chronology_case_study(
        self,
        df_ts: pd.DataFrame,
        filename: str = "7_action_window_chronology_case_study.png",
    ):
        """Plot 7: Chronological operational case study of the June 22-26, 2026 acute hypoxia event."""
        fig, (ax_rain, ax_q, ax_do) = plt.subplots(3, 1, figsize=(14, 9), sharex=True)

        t_start = pd.to_datetime("2026-06-22 00:00:00+00:00")
        t_end = pd.to_datetime("2026-06-26 12:00:00+00:00")
        sub = df_ts.loc[t_start:t_end]

        # Top: Rainfall
        ax_rain.bar(sub.index, sub["rain_mm"], width=0.03, color="#1565c0", label="ERA5 Liquid Rain (mm/h)")
        ax_rain.set_ylabel("Rain (mm/h)")
        ax_rain.set_title("AquaRehearsal-X Operational Case Study: June 22–26, 2026 Acute Hypoxia Event\nOperational Early Warning and the 35-Hour Pre-Trough Action Window")
        ax_rain.legend(loc="upper right")

        # Middle: Discharge
        ax_q.plot(sub.index, sub["discharge"], color="#00838f", linewidth=2.0, label="Discharge (cfs)")
        ax_q.set_ylabel("Discharge (cfs)")
        ax_q.legend(loc="upper right")

        # Bottom: Dissolved Oxygen
        ax_do.plot(sub.index, sub["dissolved_oxygen"], color="#2e7d32", linewidth=2.2, label="Observed DO (mg/L)")
        ax_do.axhline(5.0, color="#ff7f0e", linestyle="--", label="Standard Protection (5.0 mg/L)")
        ax_do.axhline(4.0, color="#d62728", linestyle="-.", label="Acute Impairment Standard (4.0 mg/L)")

        # Mark storm trigger and nadir
        t_storm = pd.to_datetime("2026-06-22 23:00:00+00:00")
        t_nadir = pd.to_datetime("2026-06-24 10:00:00+00:00")
        ax_do.axvline(t_storm, color="#d62728", linestyle=":", linewidth=1.8)
        ax_do.axvline(t_nadir, color="#7b1fa2", linestyle=":", linewidth=1.8)

        ax_do.axvspan(t_storm, t_nadir, color="#fff3e0", alpha=0.5, label="Action Window (35 Hours to Trough)")
        ax_do.annotate(
            "Storm Trigger\nAlert Issued", xy=(t_storm, 10.0), xytext=(pd.to_datetime("2026-06-22 10:00:00+00:00"), 11.5),
            arrowprops=dict(facecolor="black", shrink=0.05, width=1, headwidth=6),
            fontsize=10, fontweight="bold"
        )
        ax_do.annotate(
            "Acute Trough (3.65 mg/L)\nRegulatory Breach", xy=(t_nadir, 3.65), xytext=(pd.to_datetime("2026-06-24 18:00:00+00:00"), 2.5),
            arrowprops=dict(facecolor="#7b1fa2", shrink=0.05, width=1, headwidth=6),
            fontsize=10, fontweight="bold", color="#7b1fa2"
        )

        ax_do.set_ylabel("Dissolved Oxygen (mg/L)")
        ax_do.set_xlabel("Date (UTC)")
        ax_do.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
        ax_do.legend(loc="upper right")

        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 7 to %s", save_path)

    def plot_8_early_warning_reliability_diagram(
        self,
        df_events: pd.DataFrame,
        filename: str = "8_early_warning_reliability_diagram.png",
    ):
        """Plot 8: Reliability diagram for boundary-crossing probability P(DO < 5.0)."""
        fig, ax = plt.subplots(figsize=(8.5, 6))

        p_pred = df_events["p_crossing_standard_5_0"].values
        y_true = df_events["actual_breached_standard_5_0"].values.astype(float)

        bins = np.linspace(0.0, 1.0, 6)
        bin_centers = (bins[:-1] + bins[1:]) / 2.0
        emp_probs = []
        counts = []

        for i in range(len(bins) - 1):
            mask = (p_pred >= bins[i]) & (p_pred < bins[i+1])
            if np.sum(mask) > 0:
                emp_probs.append(float(np.mean(y_true[mask])))
                counts.append(int(np.sum(mask)))
            else:
                emp_probs.append(np.nan)
                counts.append(0)

        ax.plot([0, 1], [0, 1], color="gray", linestyle="--", label="Perfect Calibration")
        valid_idx = [i for i, c in enumerate(counts) if c > 0]
        ax.plot(
            bin_centers[valid_idx],
            [emp_probs[i] for i in valid_idx],
            marker="o",
            color="#0288d1",
            linewidth=2.2,
            label="STE Probability Calibration",
        )

        for i in valid_idx:
            ax.annotate(f"n={counts[i]}", (bin_centers[i], emp_probs[i] + 0.03), ha="center", fontsize=9)

        ax.set_xlabel("Forecast Boundary-Crossing Probability: P(DO < 5.0 mg/L)")
        ax.set_ylabel("Observed Empirical Breach Frequency")
        ax.set_title("Reliability Diagram: Early Warning Crossing Probability Calibration")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.05)
        ax.legend(loc="upper left")

        fig.tight_layout()
        save_path = self.output_dir / filename
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        logger.info("Saved Figure 8 to %s", save_path)
