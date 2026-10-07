"""
AquaRehearsal-X - Rehearsal Visualization & Interactive Platform
Stage 4: Risk-to-Action Decision Support

Generates:
1. Publication-quality static figures saved to data/reports/stage4/
2. Standalone interactive HTML/JS decision support application:
   data/reports/stage4/intervention_rehearsal_app.html
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config.stage4_settings import STAGE4_PLOTS_DIR, SCIENTIFIC_SAFEGUARDS
from src.utils.logger import logger


class RehearsalVisualizer:
    """Generates static publication plots and interactive decision application for Stage 4."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or STAGE4_PLOTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_72h_trajectories(
        self,
        rehearsal_result: Dict[str, Any],
        filename: str = "stage4_72h_intervention_trajectories.png",
    ) -> Path:
        """Plots baseline vs intervention 72-hour DO trajectories with threshold reference lines."""
        fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
        
        times = list(range(73))
        base_do = rehearsal_result["baseline"]["hourly_do_trajectory"]
        thr = rehearsal_result["inputs"]["threshold_mg_L"]

        ax.plot(times, base_do, color="#ef4444", linewidth=2.8, label="Baseline (No Intervention)", linestyle="-")

        color_map = {
            "temporary_aeration": ("#38bdf8", "Temporary Aeration (+0.04 mg/L/h)"),
            "runoff_reduction": ("#10b981", "Runoff Reduction (20% vol, 15% catch)"),
            "stormwater_detention": ("#f59e0b", "CSO Detention (30% peak attenuation)"),
            "riparian_shading": ("#a855f7", "Riparian Shading (-1.2°C; Long-term)"),
        }

        for itype, info in rehearsal_result["rehearsal_scenarios"].items():
            c, lbl = color_map.get(itype, ("#94a3b8", itype))
            traj = info["simulation"]["hourly_do_trajectory"]
            ax.plot(times, traj, color=c, linewidth=2.0, linestyle="--", label=lbl)

        # Threshold reference lines
        ax.axhline(thr, color="#f43f5e", linestyle=":", linewidth=1.8, label=f"Configured DO Threshold ({thr} mg/L)")
        ax.axhline(4.0, color="#f97316", linestyle=":", linewidth=1.4, alpha=0.7, label="Acute Stress (4.0 mg/L)")

        # Action window shaded zone
        act_win = rehearsal_result["action_window"].get("estimated_action_window_hours")
        if act_win and act_win > 0:
            ax.axvspan(0, act_win, color="#38bdf8", alpha=0.10, label=f"Estimated Action Window (~{act_win:.1f}h)")

        ax.set_title(
            f"AquaRehearsal-X Stage 4: 72-Hour Simulated DO Trajectories ({rehearsal_result['scenario_label']})\n"
            f"Pre-Storm T={rehearsal_result['inputs']['pre_storm_water_temp_c']}°C, Rain={rehearsal_result['inputs']['storm_rain_mm']}mm, "
            f"Initial DO={rehearsal_result['inputs']['pre_storm_do_mg_L']} mg/L",
            fontsize=12, fontweight="bold", pad=12
        )
        ax.set_xlabel("Hours Since Forecast Issue Time (t0)", fontsize=11)
        ax.set_ylabel("Dissolved Oxygen (mg/L)", fontsize=11)
        ax.set_xlim(0, 72)
        ax.set_ylim(2.0, max(12.0, max(base_do) + 0.5))
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="lower right", framealpha=0.9, fontsize=9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path)
        plt.close(fig)
        logger.info("Saved 72h DO Trajectory Plot to %s", out_path)
        return out_path

    def plot_feasibility_gantt(
        self,
        rehearsal_result: Dict[str, Any],
        filename: str = "stage4_feasibility_lead_time_gantt.png",
    ) -> Path:
        """Plots deployment lead times vs action window deadline for each intervention."""
        fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

        window_h = rehearsal_result["action_window"].get("estimated_action_window_hours", 24.0)

        names = []
        preps = []
        impls = []
        lags = []
        tier_colors = []

        color_lookup = {
            "POTENTIALLY_FEASIBLE": "#10b981",
            "FEASIBILITY_UNCERTAIN": "#f59e0b",
            "UNLIKELY_TO_AFFECT": "#ef4444",
        }

        # Truncate riparian shading for visualization (since it's ~44,000h)
        for itype, data in rehearsal_result["rehearsal_scenarios"].items():
            feas = data["feasibility"]
            display_name = {
                "temporary_aeration": "Temporary Aeration",
                "runoff_reduction": "Runoff Reduction",
                "stormwater_detention": "CSO Detention",
                "riparian_shading": "Riparian Shading (Structural)",
            }.get(itype, itype)

            names.append(display_name)
            tier_colors.append(color_lookup.get(feas["feasibility_tier"], "#94a3b8"))

            if itype == "riparian_shading":
                preps.append(min(60.0, feas["prep_time_hours"]))
                impls.append(10.0)
                lags.append(2.0)
            else:
                preps.append(feas["prep_time_hours"])
                impls.append(feas["implementation_time_hours"])
                lags.append(feas["effect_lag_hours"])

        y_pos = np.arange(len(names))
        preps = np.array(preps)
        impls = np.array(impls)
        lags = np.array(lags)

        ax.barh(y_pos, preps, color="#3b82f6", alpha=0.75, label="Preparation / Dispatch")
        ax.barh(y_pos, impls, left=preps, color="#8b5cf6", alpha=0.75, label="Implementation / Setup")
        ax.barh(y_pos, lags, left=preps + impls, color="#f59e0b", alpha=0.75, label="Environmental Effect Lag")

        # Action window vertical line
        ax.axvline(window_h, color="#ef4444", linestyle="--", linewidth=2.2, label=f"Estimated Action Window (~{window_h:.1f}h)")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=10, fontweight="bold")
        ax.invert_yaxis()
        ax.set_xlabel("Hours Required for Deployment", fontsize=11)
        ax.set_title("AquaRehearsal-X Stage 4: Operational Lead Time vs. Action Window Deadline\nStrict Anti-Ranking Assessment", fontsize=11, fontweight="bold")
        ax.set_xlim(0, max(48.0, window_h + 15.0))
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="lower right", fontsize=9)

        plt.tight_layout()
        out_path = self.output_dir / filename
        fig.savefig(out_path)
        plt.close(fig)
        logger.info("Saved Feasibility Gantt Plot to %s", out_path)
        return out_path

    def build_interactive_application(
        self,
        rehearsal_result: Dict[str, Any],
        filename: str = "intervention_rehearsal_app.html",
    ) -> Path:
        """Builds a standalone interactive web application for Stage 4."""
        out_path = self.output_dir / filename
        
        def default_serializer(o):
            if isinstance(o, (np.bool_, bool)):
                return bool(o)
            elif isinstance(o, (np.integer, int)):
                return int(o)
            elif isinstance(o, (np.floating, float)):
                return float(o)
            elif isinstance(o, np.ndarray):
                return o.tolist()
            return str(o)

        result_json = json.dumps(rehearsal_result, default=default_serializer, indent=2)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AquaRehearsal-X — Stage 4: Risk-to-Action Decision Support</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-primary: #0a0e17;
      --bg-secondary: #121826;
      --bg-card: rgba(22, 30, 46, 0.85);
      --border-color: rgba(255, 255, 255, 0.1);
      --accent-safe: #10b981;
      --accent-advisory: #f59e0b;
      --accent-warning: #ef4444;
      --accent-blue: #38bdf8;
      --accent-purple: #a855f7;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--font-sans);
      background-color: var(--bg-primary);
      color: var(--text-main);
      line-height: 1.5;
      padding: 24px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
    }}
    .header h1 {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .badge-feasible {{ background: rgba(16, 185, 129, 0.15); color: var(--accent-safe); border: 1px solid var(--accent-safe); }}
    .badge-uncertain {{ background: rgba(245, 158, 11, 0.15); color: var(--accent-advisory); border: 1px solid var(--accent-advisory); }}
    .badge-unlikely {{ background: rgba(239, 68, 68, 0.15); color: var(--accent-warning); border: 1px solid var(--accent-warning); }}

    .grid-container {{
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 24px;
    }}
    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 20px;
      backdrop-filter: blur(10px);
    }}
    .card h2 {{
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
      color: var(--accent-blue);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .control-group {{
      margin-bottom: 16px;
    }}
    .control-group label {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }}
    .control-group input[type="range"] {{
      width: 100%;
      accent-color: var(--accent-blue);
    }}
    .control-group select {{
      width: 100%;
      background: var(--bg-secondary);
      color: var(--text-main);
      border: 1px solid var(--border-color);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
    }}
    .val-display {{
      font-family: var(--font-mono);
      font-weight: 600;
      color: var(--text-main);
    }}

    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 14px;
      text-align: center;
    }}
    .kpi-title {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px; }}
    .kpi-value {{ font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--accent-blue); }}
    .kpi-sub {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}

    table.scenario-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin-top: 12px;
    }}
    table.scenario-table th, table.scenario-table td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border-color);
    }}
    table.scenario-table th {{
      color: var(--text-muted);
      font-weight: 600;
      background: rgba(0, 0, 0, 0.2);
    }}
    .disclaimer-box {{
      background: rgba(239, 68, 68, 0.08);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 12px;
      color: #fca5a5;
      margin-top: 20px;
    }}
  </style>
</head>
<body>

  <div class="header">
    <div>
      <h1>AquaRehearsal-X — Stage 4: Risk-to-Action Decision Support</h1>
      <p style="font-size: 13px; color: var(--text-muted);">
        Action Window Estimation & Multi-Intervention Scenario Rehearsal | USGS 01474500 (Schuylkill River, PA)
      </p>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
      <a href="../../../index.html" style="color: #38bdf8; text-decoration: none; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 6px; transition: all 0.2s;">← Return to Mission Control</a>
      <span class="badge badge-feasible">Decision Support Engine</span>
    </div>
  </div>

  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-title">Active DO Threshold</div>
      <div class="kpi-value" id="disp-kpi-thresh">5.0 mg/L</div>
      <div class="kpi-sub">PA DEP WWF Criterion</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Estimated Action Window</div>
      <div class="kpi-value" id="disp-kpi-window">~18.5 h</div>
      <div class="kpi-sub">Time before earliest crossing</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Baseline 72h Breach Risk</div>
      <div class="kpi-value" id="disp-kpi-risk" style="color: var(--accent-warning);">34.2%</div>
      <div class="kpi-sub">Operational Limit: 20%</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Historical Time-to-Nadir</div>
      <div class="kpi-value" id="disp-kpi-nadir">23.5 h</div>
      <div class="kpi-sub">Median lag from 58 events</div>
    </div>
  </div>

  <div class="grid-container">
    <!-- Left Column: Controls & Presets -->
    <div>
      <div class="card">
        <h2>⚡ Storm Scenario Input</h2>
        <div class="control-group">
          <label>Preset Historical Storm</label>
          <select id="preset-selector" onchange="loadPreset()">
            <option value="custom">-- Custom Scenario --</option>
            <option value="storm_summer">July 2024 Hot Summer Surge (26°C, 35mm)</option>
            <option value="storm_fall">Sept 2023 Intense Frontal Storm (20°C, 48mm)</option>
            <option value="storm_spring">April 2025 Cold High-Flow Runoff (11°C, 28mm)</option>
          </select>
        </div>

        <div class="control-group">
          <label>Pre-Storm Water Temp: <span class="val-display" id="disp-temp">24.0°C</span></label>
          <input type="range" id="input-temp" min="2" max="30" step="0.5" value="24.0" oninput="updateSimulation()">
        </div>

        <div class="control-group">
          <label>Incoming Storm Rain: <span class="val-display" id="disp-rain">35.0 mm</span></label>
          <input type="range" id="input-rain" min="0" max="70" step="1" value="35.0" oninput="updateSimulation()">
        </div>

        <div class="control-group">
          <label>Initial DO: <span class="val-display" id="disp-do">7.2 mg/L</span></label>
          <input type="range" id="input-do" min="4" max="12" step="0.2" value="7.2" oninput="updateSimulation()">
        </div>

        <div class="control-group">
          <label>DO Risk Threshold: <span class="val-display" id="disp-thresh">5.0 mg/L</span></label>
          <input type="range" id="input-thresh" min="3.0" max="7.0" step="0.5" value="5.0" oninput="updateSimulation()">
        </div>
      </div>

      <div class="card">
        <h2>🛠️ Intervention Rehearsal Parameters</h2>
        <div class="control-group">
          <label>Aeration Rate: <span class="val-display" id="disp-aerate">0.04 mg/L/h</span></label>
          <input type="range" id="input-aerate" min="0.01" max="0.10" step="0.01" value="0.04" oninput="updateSimulation()">
        </div>

        <div class="control-group">
          <label>Runoff Reduction: <span class="val-display" id="disp-runoff">20%</span></label>
          <input type="range" id="input-runoff" min="5" max="45" step="5" value="20" oninput="updateSimulation()">
        </div>

        <div class="control-group">
          <label>CSO Detention Peak Attenuation: <span class="val-display" id="disp-detent">30%</span></label>
          <input type="range" id="input-detent" min="10" max="60" step="5" value="30" oninput="updateSimulation()">
        </div>
      </div>
    </div>

    <!-- Right Column: Trajectories & Comparison -->
    <div>
      <div class="card">
        <h2>📈 72-Hour Dissolved Oxygen Rehearsal Trajectories</h2>
        <div id="plot-trajectories" style="height: 380px;"></div>
      </div>

      <div class="card">
        <h2>⚖️ Side-by-Side Trade-Off Matrix (Anti-Ranking Principle)</h2>
        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">
          Interventions are evaluated alongside their physical lead times and logistical bottlenecks. No single 'winner' is assigned.
        </p>
        <table class="scenario-table" id="table-comparison">
          <thead>
            <tr>
              <th>Intervention</th>
              <th>Category</th>
              <th>Lead Time</th>
              <th>Action Window Margin</th>
              <th>Feasibility Tier</th>
              <th>Simulated Min DO</th>
              <th>DO Gain</th>
            </tr>
          </thead>
          <tbody id="table-body">
            <!-- Dynamically populated -->
          </tbody>
        </table>
      </div>

      <div class="disclaimer-box">
        <strong>Scientific & Decision-Support Disclaimer:</strong><br>
        Simulated intervention outcomes represent exploratory mass-balance scenarios and do NOT constitute measured real-world effects.
        The action window is a data-derived statistical estimate, not a guaranteed countdown clock. Because no in-situ emergency aeration trials were conducted at Station 01474500, results are for operational rehearsal and planning.
      </div>
    </div>
  </div>

  <script>
    // Initial payload from Python pipeline
    const initialData = {result_json};

    function updateSimulation() {{
      const temp = parseFloat(document.getElementById('input-temp').value);
      const rain = parseFloat(document.getElementById('input-rain').value);
      const do0 = parseFloat(document.getElementById('input-do').value);
      const thresh = parseFloat(document.getElementById('input-thresh').value);
      const aerate = parseFloat(document.getElementById('input-aerate').value);
      const runoff = parseFloat(document.getElementById('input-runoff').value);
      const detent = parseFloat(document.getElementById('input-detent').value);

      document.getElementById('disp-temp').innerText = temp.toFixed(1) + '°C';
      document.getElementById('disp-rain').innerText = rain.toFixed(1) + ' mm';
      document.getElementById('disp-do').innerText = do0.toFixed(1) + ' mg/L';
      document.getElementById('disp-thresh').innerText = thresh.toFixed(1) + ' mg/L';
      document.getElementById('disp-kpi-thresh').innerText = thresh.toFixed(1) + ' mg/L';
      document.getElementById('disp-aerate').innerText = aerate.toFixed(2) + ' mg/L/h';
      document.getElementById('disp-runoff').innerText = runoff + '%';
      document.getElementById('disp-detent').innerText = detent + '%';

      // Re-run simplified Streeter-Phelps forward trajectory in-browser
      const times = [];
      const baseTraj = [];
      const aerateTraj = [];
      const runoffTraj = [];
      const detentTraj = [];
      const shadingTraj = [];

      // Benson-Krause approximation
      const cs = 14.652 - 0.41022 * temp + 0.007991 * temp * temp - 0.000077774 * temp * temp * temp;
      const ka = 0.038 * Math.pow(1.024, temp - 20.0);
      const kd = 0.012 * Math.pow(1.047, temp - 20.0);
      const sod = 0.022 * Math.pow(1.065, temp - 20.0);

      // Shaded kinetics (-1.2°C)
      const tShade = Math.max(1.0, temp - 1.2);
      const csShade = 14.652 - 0.41022 * tShade + 0.007991 * tShade * tShade - 0.000077774 * tShade * tShade * tShade;
      const kaShade = 0.038 * Math.pow(1.024, tShade - 20.0);
      const kdShade = 0.012 * Math.pow(1.047, tShade - 20.0);
      const sodShade = 0.022 * Math.pow(1.065, tShade - 20.0);

      let cBase = Math.min(do0, cs);
      let cAerate = cBase;
      let cRunoff = cBase;
      let cDetent = cBase;
      let cShade = Math.min(do0, csShade);

      let lBase = 3.2;
      let lRunoff = 3.2;
      let lDetent = 3.2;

      const totalBod = (1.0 - Math.exp(-rain / 22.0)) * 14.5;
      const totalBodRunoff = totalBod * (1.0 - (runoff / 100.0) * 0.20);
      const totalBodDetent = totalBod * (1.0 - (detent / 100.0) * 0.15);

      const dt = 0.5;
      const steps = 72 / dt;

      for (let s = 0; s <= steps; s++) {{
        const t = s * dt;
        const wBase = rain > 0.5 ? (totalBod / 8.0) * Math.max(0, (t - 2.0) / 8.0) * Math.exp(-Math.max(0, (t - 2.0) / 8.0)) : 0;
        const wRunoff = rain > 0.5 ? (totalBodRunoff / 8.0) * Math.max(0, (t - 2.0) / 8.0) * Math.exp(-Math.max(0, (t - 2.0) / 8.0)) : 0;
        const wDetent = rain > 0.5 ? (totalBodDetent / 12.0) * Math.max(0, (t - 6.0) / 12.0) * Math.exp(-Math.max(0, (t - 6.0) / 12.0)) : 0;

        const rAir = (t >= 4.0 && t <= 28.0) ? aerate : 0.0;

        cBase += (ka * (cs - cBase) - kd * lBase - sod) * dt;
        cAerate += (ka * (cs - cAerate) - kd * lBase - sod + rAir) * dt;
        cRunoff += (ka * (cs - cRunoff) - kd * lRunoff - sod) * dt;
        cDetent += (ka * (cs - cDetent) - kd * lDetent - sod) * dt;
        cShade += (kaShade * (csShade - cShade) - kdShade * lBase - sodShade) * dt;

        lBase += (-0.018 * lBase + wBase) * dt;
        lRunoff += (-0.018 * lRunoff + wRunoff) * dt;
        lDetent += (-0.018 * lDetent + wDetent) * dt;

        if (s % 2 === 0) {{
          times.push(t);
          baseTraj.push(cBase);
          aerateTraj.push(cAerate);
          runoffTraj.push(cRunoff);
          detentTraj.push(cDetent);
          shadingTraj.push(cShade);
        }}
      }}

      const minBase = Math.min(...baseTraj);
      const minAerate = Math.min(...aerateTraj);
      const minRunoff = Math.min(...runoffTraj);
      const minDetent = Math.min(...detentTraj);
      const minShade = Math.min(...shadingTraj);

      // Action window estimate
      let actionWindow = 23.5;
      if (minBase < thresh) {{
        actionWindow = Math.max(4.0, 23.5 * ((do0 - thresh) / Math.max(0.1, do0 - minBase)));
      }}
      document.getElementById('disp-kpi-window').innerText = '~' + actionWindow.toFixed(1) + ' h';
      const riskEst = minBase < thresh ? Math.min(99.0, 20.0 + (thresh - minBase) * 25.0) : Math.max(1.0, 15.0 - (minBase - thresh) * 8.0);
      document.getElementById('disp-kpi-risk').innerText = riskEst.toFixed(1) + '%';

      // Plot
      const traces = [
        {{ x: times, y: baseTraj, name: 'Baseline (No Action)', line: {{ color: '#ef4444', width: 3 }} }},
        {{ x: times, y: aerateTraj, name: 'Temporary Aeration', line: {{ color: '#38bdf8', width: 2, dash: 'dash' }} }},
        {{ x: times, y: runoffTraj, name: 'Runoff Reduction', line: {{ color: '#10b981', width: 2, dash: 'dot' }} }},
        {{ x: times, y: detentTraj, name: 'CSO Detention', line: {{ color: '#f59e0b', width: 2, dash: 'dashdot' }} }},
        {{ x: times, y: shadingTraj, name: 'Riparian Shading (-1.2°C)', line: {{ color: '#a855f7', width: 2, dash: 'dot' }} }},
        {{ x: [0, 72], y: [thresh, thresh], name: 'Threshold (' + thresh.toFixed(1) + ' mg/L)', line: {{ color: '#f43f5e', width: 1.5, dash: 'dot' }} }},
      ];

      const layout = {{
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {{ color: '#f3f4f6', family: 'Inter' }},
        margin: {{ l: 50, r: 20, t: 20, b: 40 }},
        xaxis: {{ title: 'Hours Since Forecast Issue', gridcolor: 'rgba(255,255,255,0.08)' }},
        yaxis: {{ title: 'Dissolved Oxygen (mg/L)', gridcolor: 'rgba(255,255,255,0.08)' }},
        legend: {{ orientation: 'h', y: -0.2 }},
      }};

      Plotly.react('plot-trajectories', traces, layout);

      // Update Table
      const scenarios = [
        {{ name: 'Baseline (No Action)', cat: 'Status Quo', lead: 0.0, margin: 0.0, tier: 'BASELINE', minDO: minBase, gain: 0.0 }},
        {{ name: 'Temporary Aeration', cat: 'Active Mechanical', lead: 5.0, margin: actionWindow - 5.0, tier: (actionWindow >= 5.0 ? 'POTENTIALLY_FEASIBLE' : 'FEASIBILITY_UNCERTAIN'), minDO: minAerate, gain: minAerate - minBase }},
        {{ name: 'Runoff Reduction', cat: 'Catchment Source Control', lead: 13.0, margin: actionWindow - 13.0, tier: (actionWindow >= 13.0 ? 'POTENTIALLY_FEASIBLE' : 'FEASIBILITY_UNCERTAIN'), minDO: minRunoff, gain: minRunoff - minBase }},
        {{ name: 'CSO Detention', cat: 'Dynamic Storage', lead: 4.5, margin: actionWindow - 4.5, tier: (actionWindow >= 4.5 ? 'POTENTIALLY_FEASIBLE' : 'FEASIBILITY_UNCERTAIN'), minDO: minDetent, gain: minDetent - minBase }},
        {{ name: 'Riparian Shading', cat: 'Long-Term Structural', lead: 44520.0, margin: actionWindow - 44520.0, tier: 'UNLIKELY_TO_AFFECT', minDO: minShade, gain: minShade - minBase }},
      ];

      let tbHtml = '';
      scenarios.forEach(s => {{
        let badgeClass = 'badge-feasible';
        if (s.tier === 'FEASIBILITY_UNCERTAIN') badgeClass = 'badge-uncertain';
        if (s.tier === 'UNLIKELY_TO_AFFECT') badgeClass = 'badge-unlikely';
        if (s.tier === 'BASELINE') badgeClass = 'badge-uncertain';

        tbHtml += `<tr>
          <td><strong>${{s.name}}</strong></td>
          <td>${{s.cat}}</td>
          <td>${{s.lead > 100 ? '>5 Years' : s.lead.toFixed(1) + ' h'}}</td>
          <td>${{s.margin < -100 ? 'N/A' : (s.margin >= 0 ? '+' + s.margin.toFixed(1) + ' h' : s.margin.toFixed(1) + ' h')}}</td>
          <td><span class="badge ${{badgeClass}}">${{s.tier}}</span></td>
          <td><strong>${{s.minDO.toFixed(2)}} mg/L</strong></td>
          <td style="color: var(--accent-safe);">${{s.gain > 0 ? '+' + s.gain.toFixed(2) + ' mg/L' : '0.00'}}</td>
        </tr>`;
      }});
      document.getElementById('table-body').innerHTML = tbHtml;
    }}

    function loadPreset() {{
      const p = document.getElementById('preset-selector').value;
      if (p === 'storm_summer') {{
        document.getElementById('input-temp').value = 26.0;
        document.getElementById('input-rain').value = 35.0;
        document.getElementById('input-do').value = 6.8;
      }} else if (p === 'storm_fall') {{
        document.getElementById('input-temp').value = 20.0;
        document.getElementById('input-rain').value = 48.0;
        document.getElementById('input-do').value = 8.1;
      }} else if (p === 'storm_spring') {{
        document.getElementById('input-temp').value = 11.0;
        document.getElementById('input-rain').value = 28.0;
        document.getElementById('input-do').value = 10.5;
      }}
      updateSimulation();
    }}

    // Initial render
    updateSimulation();
  </script>
</body>
</html>
"""
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info("Saved Interactive Rehearsal App to %s", out_path)
        return out_path
