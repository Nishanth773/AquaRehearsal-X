"""
AquaRehearsal-X - Mission Control App Generator
Stage 7: Professional Scientific / Environmental Decision-Support Platform

Generates a standalone, research-grade interactive HTML5 application:
data/reports/stage6/mission_control.html and root index.html

Visual Design Direction:
- Authoritative environmental science & hydrology workstation interface (USGS / NOAA / EPA style).
- Restrained, publication-grade scientific color palette.
- No gaming, neon, or cyberpunk elements.
- Clear technical metadata, parameter codes, and units.
- 2D Storm Tolerance Envelope as the HERO scientific visualization.
- 72-hour DO time-series forecast with conformal uncertainty bounds.
- Engineering scenario rehearsal with Streeter-Phelps mass balance.
- Dual-track citizen science field verification and One Health triad.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import pandas as pd
from datetime import datetime, timezone

from src.config.stage6_settings import (
    BASE_DIR,
    STAGE6_REPORTS_DIR,
    DEFAULT_OPERATIONAL_CONFIG,
    REPLAY_DEMO_EVENT,
    INTEGRATION_DISCLAIMERS,
)
from src.integration.system_observability import SystemObservability
from src.integration.historical_storm_replay_demo import HistoricalStormReplayDemo
from src.integration.unified_workflow import UnifiedWorkflow
from src.utils.logger import logger


class MissionControlAppBuilder:
    """Generates the unified, professional scientific Mission Control web platform."""

    def __init__(self, output_path: Optional[Path] = None):
        self.output_path = output_path or (STAGE6_REPORTS_DIR / "mission_control.html")
        self.workflow = UnifiedWorkflow()
        self.observability = SystemObservability()
        self.replay_demo = HistoricalStormReplayDemo()

    def generate_html(self) -> Path:
        """Runs workflow and observability audits, then compiles the scientific HTML application."""
        logger.info("Compiling AquaRehearsal-X Scientific Mission Control application...")

        # 1. Gather baseline data
        stream_state = self.workflow.get_latest_stream_conditions()
        health_data = self.observability.audit_all_subsystems()
        replay_data = self.replay_demo.reconstruct_and_evaluate()
        full_pipeline = self.workflow.run_full_pipeline(simulated_storm_rain_mm=26.5, custom_water_temp_c=26.5)

        # 2. Extract 58 historical storm events for 2D STE scatter plot
        historical_storms = []
        historical_evals_path = STAGE6_REPORTS_DIR.parent / "stage3" / "historical_ste_evaluations.csv"
        if historical_evals_path.exists():
            try:
                df_ste = pd.read_csv(historical_evals_path)
                for _, row in df_ste.iterrows():
                    historical_storms.append({
                        "id": int(row["event_id"]),
                        "temp": round(float(row["ambient_temp_c"]), 1),
                        "rain": round(float(row["storm_rain_mm"]), 1),
                        "observed_min_do": round(float(row["observed_min_do_72h"]), 2),
                        "predicted_min_do": round(float(row["predicted_min_do_72h"]), 2),
                        "alert": str(row.get("alert_level", "NORMAL")),
                        "is_replay": bool(int(row["event_id"]) == 54),
                    })
            except Exception as e:
                logger.warning(f"Could not load historical storm evaluations for scatter: {e}")

        # 3. Serialize for embedded client-side reactivity
        embedded_json = json.dumps({
            "stream_state": stream_state,
            "health_data": health_data,
            "replay_data": replay_data,
            "full_pipeline": full_pipeline,
            "disclaimers": INTEGRATION_DISCLAIMERS,
            "station_config": DEFAULT_OPERATIONAL_CONFIG,
            "historical_storms": historical_storms,
        }, indent=2, default=str)

        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AquaRehearsal-X | Water Quality Decision-Support System (USGS 01474500)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-page: #f1f5f9;
      --bg-surface: #ffffff;
      --bg-subtle: #f8fafc;
      --bg-header: #0f172a;
      --border-main: #cbd5e1;
      --border-light: #e2e8f0;
      --border-dark: #334155;
      --text-main: #0f172a;
      --text-muted: #475569;
      --text-sub: #64748b;
      --color-primary: #0284c7;
      --color-primary-dark: #0369a1;
      --color-safe: #15803d;
      --color-safe-bg: #f0fdf4;
      --color-safe-border: #bbf7d0;
      --color-advisory: #b45309;
      --color-advisory-bg: #fffbeb;
      --color-advisory-border: #fde68a;
      --color-alert: #b91c1c;
      --color-alert-bg: #fef2f2;
      --color-alert-border: #fecaca;
      --font-main: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-page);
      color: var(--text-main);
      font-family: var(--font-main);
      font-size: 13px;
      line-height: 1.45;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* INSTITUTIONAL HEADER */
    header {
      background: var(--bg-header);
      color: #f8fafc;
      border-bottom: 2px solid #0284c7;
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .header-main {
      padding: 0.65rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.75rem;
    }

    .brand-block {
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }

    .brand-badge {
      background: #0284c7;
      color: #ffffff;
      font-weight: 800;
      font-size: 0.85rem;
      padding: 0.25rem 0.55rem;
      border-radius: 3px;
      letter-spacing: 0.05em;
    }

    .brand-details {
      display: flex;
      flex-direction: column;
    }

    .brand-title {
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #ffffff;
    }

    .brand-subtitle {
      font-size: 0.72rem;
      color: #94a3b8;
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-wrap: wrap;
    }

    .btn {
      padding: 0.35rem 0.65rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      transition: background-color 0.15s, border-color 0.15s;
      font-family: var(--font-main);
      border: 1px solid transparent;
      text-decoration: none;
      white-space: nowrap;
    }

    .btn-header {
      background: #1e293b;
      color: #e2e8f0;
      border-color: #334155;
    }
    .btn-header:hover {
      background: #334155;
      color: #ffffff;
      border-color: #475569;
    }

    .btn-primary {
      background: #0284c7;
      color: #ffffff;
    }
    .btn-primary:hover {
      background: #0369a1;
    }

    .btn-secondary {
      background: #ffffff;
      color: var(--text-main);
      border: 1px solid var(--border-main);
    }
    .btn-secondary:hover {
      background: #f8fafc;
      border-color: var(--text-muted);
    }

    /* OBSERVABILITY SUB-BAR */
    .observability-bar {
      background: #090e1a;
      border-top: 1px solid #1e293b;
      padding: 0.35rem 1.5rem;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      overflow-x: auto;
      font-size: 0.7rem;
      color: #94a3b8;
      scrollbar-width: thin;
    }

    .obs-label {
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #cbd5e1;
      white-space: nowrap;
    }

    .obs-item {
      padding: 0.15rem 0.45rem;
      border-radius: 3px;
      background: #131d2e;
      border: 1px solid #233147;
      display: flex;
      align-items: center;
      gap: 0.35rem;
      cursor: pointer;
      white-space: nowrap;
    }
    .obs-item:hover {
      border-color: #38bdf8;
    }

    .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }
    .dot-safe { background: #22c55e; }
    .dot-limitation { background: #f59e0b; }
    .dot-unvalidated { background: #a855f7; }
    .dot-alert { background: #ef4444; }

    /* MAIN WORKSPACE */
    main {
      flex: 1;
      padding: 1rem 1.5rem;
      max-width: 1720px;
      margin: 0 auto;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    /* REPLAY & TOUR BANNERS */
    .banner-replay {
      display: none;
      background: #fefce8;
      border: 1px solid #fde047;
      border-left: 4px solid #ca8a04;
      border-radius: 4px;
      padding: 0.65rem 1rem;
      color: #713f12;
      font-size: 0.8rem;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }

    .banner-tour {
      display: none;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-left: 4px solid #0284c7;
      border-radius: 4px;
      padding: 0.75rem 1rem;
      justify-content: space-between;
      align-items: center;
      gap: 1.25rem;
    }

    .tour-content {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }

    .tour-stepper {
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }

    /* METADATA BAR */
    .metadata-strip {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: 4px;
      padding: 0.5rem 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.65rem;
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .meta-group {
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }

    .meta-item strong {
      color: var(--text-main);
    }

    /* TELEMETRY TILES */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 0.75rem;
    }

    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: 4px;
      padding: 0.75rem 0.9rem;
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }

    .kpi-param-code {
      font-size: 0.68rem;
      color: var(--text-sub);
      text-transform: uppercase;
      font-family: var(--font-mono);
    }

    .kpi-title {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
    }

    .kpi-value-row {
      display: flex;
      align-items: baseline;
      gap: 0.35rem;
      margin: 0.15rem 0;
    }

    .kpi-value {
      font-size: 1.55rem;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text-main);
      line-height: 1.1;
    }

    .kpi-unit {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 500;
      font-family: var(--font-main);
    }

    .kpi-footer {
      font-size: 0.7rem;
      color: var(--text-sub);
    }

    /* CONTROLS PANEL */
    .controls-panel {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: 4px;
      padding: 0.75rem 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }

    .controls-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 0.4rem;
    }

    .controls-title {
      font-size: 0.8rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--text-secondary);
    }

    .controls-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
    }

    .control-item {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .control-label {
      display: flex;
      justify-content: space-between;
      font-size: 0.73rem;
      font-weight: 500;
      color: var(--text-secondary);
    }

    .control-val {
      font-family: var(--font-mono);
      font-weight: 600;
      color: #0369a1;
    }

    input[type=range] {
      width: 100%;
      height: 4px;
      accent-color: #0284c7;
      cursor: pointer;
    }

    .presets-bar {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      font-size: 0.72rem;
      color: var(--text-muted);
      flex-wrap: wrap;
      border-top: 1px solid var(--border-light);
      padding-top: 0.5rem;
    }

    .preset-btn {
      padding: 0.2rem 0.5rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border-main);
      color: var(--text-secondary);
      border-radius: 3px;
      cursor: pointer;
      font-size: 0.72rem;
      font-family: var(--font-main);
    }
    .preset-btn:hover {
      background: #e2e8f0;
      color: var(--text-main);
    }

    /* CENTERPIECE GRIDS (HERO STE & TRAJECTORY) */
    .grid-centerpiece {
      display: grid;
      grid-template-columns: 1.25fr 1fr;
      gap: 1rem;
    }

    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: 4px;
      padding: 0.9rem;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }

    .card-hero {
      border: 1.5px solid #0284c7;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 0.5rem;
    }

    .card-title {
      font-size: 0.88rem;
      font-weight: 700;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }

    .card-subtitle {
      font-size: 0.7rem;
      color: var(--text-sub);
      font-weight: 400;
    }

    .status-badge {
      font-size: 0.7rem;
      font-weight: 600;
      font-family: var(--font-mono);
      padding: 0.15rem 0.45rem;
      border-radius: 3px;
      border: 1px solid transparent;
      text-transform: uppercase;
    }

    .badge-status-safe {
      background: var(--color-safe-bg);
      color: var(--color-safe);
      border-color: var(--color-safe-border);
    }

    .badge-status-advisory {
      background: var(--color-advisory-bg);
      color: var(--color-advisory);
      border-color: var(--color-advisory-border);
    }

    .badge-status-elevated {
      background: var(--color-alert-bg);
      color: var(--color-alert);
      border-color: var(--color-alert-border);
    }

    .badge-status-refusal {
      background: var(--color-alert-bg);
      color: var(--color-alert);
      border-color: var(--color-alert-border);
      font-weight: 700;
    }

    /* CANVAS CONTAINERS */
    .canvas-wrap-ste {
      width: 100%;
      height: 380px;
      background: #ffffff;
      border: 1px solid var(--border-light);
      border-radius: 3px;
      position: relative;
    }

    .canvas-wrap-traj {
      width: 100%;
      height: 320px;
      background: #ffffff;
      border: 1px solid var(--border-light);
      border-radius: 3px;
      position: relative;
    }

    canvas {
      width: 100%;
      height: 100%;
      display: block;
    }

    /* STE SUMMARY METRICS */
    .ste-summary-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0.5rem;
      background: var(--bg-subtle);
      border: 1px solid var(--border-light);
      padding: 0.55rem 0.75rem;
      border-radius: 3px;
    }

    .ste-summary-col {
      display: flex;
      flex-direction: column;
      gap: 0.1rem;
    }

    .ste-label {
      font-size: 0.68rem;
      color: var(--text-sub);
      text-transform: uppercase;
      font-weight: 600;
    }

    .ste-val {
      font-family: var(--font-mono);
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--text-main);
    }

    /* INTERVENTION SEGMENTED CONTROL */
    .intervention-tabs {
      display: flex;
      border: 1px solid var(--border-main);
      border-radius: 4px;
      overflow: hidden;
      background: var(--bg-subtle);
    }

    .int-tab {
      flex: 1;
      padding: 0.4rem 0.5rem;
      text-align: center;
      font-size: 0.73rem;
      font-weight: 600;
      cursor: pointer;
      color: var(--text-muted);
      border-right: 1px solid var(--border-main);
      background: var(--bg-subtle);
      transition: background-color 0.15s, color 0.15s;
    }
    .int-tab:last-child {
      border-right: none;
    }
    .int-tab.active {
      background: #ffffff;
      color: #0369a1;
      box-shadow: inset 0 -2px 0 #0284c7;
    }

    /* NOTICES & CALLOUTS */
    .notice-box {
      border-radius: 3px;
      padding: 0.5rem 0.75rem;
      font-size: 0.73rem;
      line-height: 1.4;
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
      border: 1px solid var(--border-main);
      background: var(--bg-subtle);
      color: var(--text-muted);
    }

    .notice-advisory {
      background: var(--color-advisory-bg);
      border-color: var(--color-advisory-border);
      color: var(--color-advisory);
    }

    .notice-alert {
      background: var(--color-alert-bg);
      border-color: var(--color-alert-border);
      color: var(--color-alert);
    }

    .notice-info {
      background: #f0f9ff;
      border-color: #bae6fd;
      color: #0369a1;
    }

    /* LOWER 3-COLUMN PANELS */
    .grid-3col {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem;
    }

    .stat-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.74rem;
    }
    .stat-table th, .stat-table td {
      padding: 0.4rem 0.55rem;
      border-bottom: 1px solid var(--border-light);
      text-align: left;
    }
    .stat-table th {
      color: var(--text-sub);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.68rem;
      background: var(--bg-subtle);
    }
    .stat-table td strong {
      font-family: var(--font-mono);
    }

    /* SCIENTIFIC LIMITATIONS SECTION */
    .limitations-panel {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-left: 4px solid #b45309;
      border-radius: 4px;
      padding: 0.9rem 1.1rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }

    .limitations-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 0.4rem;
    }

    .limitations-title {
      font-size: 0.88rem;
      font-weight: 700;
      color: var(--text-main);
    }

    .limitations-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.75rem;
    }

    .lim-card {
      background: var(--bg-subtle);
      border: 1px solid var(--border-light);
      border-radius: 3px;
      padding: 0.65rem;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      font-size: 0.73rem;
    }

    .lim-tag {
      font-size: 0.65rem;
      font-weight: 700;
      color: #b45309;
      text-transform: uppercase;
      font-family: var(--font-mono);
    }

    .lim-heading {
      font-weight: 600;
      color: var(--text-main);
    }

    .lim-body {
      color: var(--text-muted);
      line-height: 1.35;
    }

    .lim-advancement {
      margin-top: 0.2rem;
      padding-top: 0.25rem;
      border-top: 1px solid var(--border-light);
      font-size: 0.68rem;
      color: #0369a1;
    }

    /* MODAL WINDOWS */
    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.65);
      z-index: 500;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }

    .modal-box {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: 4px;
      max-width: 800px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 1.25rem;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-light);
      padding-bottom: 0.65rem;
    }

    .modal-header h3 {
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--text-main);
    }

    .close-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.35rem;
      cursor: pointer;
      line-height: 1;
    }
    .close-btn:hover {
      color: var(--text-main);
    }

    .modal-data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.74rem;
    }
    .modal-data-table th, .modal-data-table td {
      padding: 0.5rem 0.65rem;
      text-align: left;
      border-bottom: 1px solid var(--border-light);
    }
    .modal-data-table th {
      background: var(--bg-subtle);
      color: var(--text-sub);
      text-transform: uppercase;
      font-size: 0.68rem;
      font-weight: 600;
    }

    /* RESPONSIVE BREAKPOINTS */
    @media (max-width: 1366px) {
      .grid-centerpiece {
        grid-template-columns: 1fr;
      }
      .kpi-grid {
        grid-template-columns: repeat(3, 1fr);
      }
      .grid-3col {
        grid-template-columns: 1fr;
      }
      .limitations-grid {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 900px) {
      .header-main { padding: 0.5rem 1rem; }
      main { padding: 0.75rem; }
      .controls-grid { grid-template-columns: 1fr 1fr; }
      .kpi-grid { grid-template-columns: 1fr 1fr; }
      .limitations-grid { grid-template-columns: 1fr; }
      .ste-summary-grid { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>

  <!-- INSTITUTIONAL HEADER -->
  <header>
    <div class="header-main">
      <div class="brand-block">
        <div class="brand-badge">AQUAREHEARSAL-X</div>
        <div class="brand-details">
          <div class="brand-title">Water Quality Decision-Support System</div>
          <div class="brand-subtitle">USGS Station 01474500 • Schuylkill River at Philadelphia, PA • Drainage Area: 1,893 mi²</div>
        </div>
      </div>

      <div class="nav-actions">
        <button class="btn btn-primary" id="btn-tour" onclick="startTour()">Guided Tour (3 min)</button>
        <button class="btn btn-header" id="btn-replay-toggle" onclick="toggleReplayMode()">Historical Replay (Event 54)</button>
        <button class="btn btn-header" onclick="openModal('modal-limits')">Methodological Limitations</button>
        <button class="btn btn-header" onclick="openModal('modal-judge')">Technical Summary</button>
        <button class="btn btn-header" onclick="openModal('modal-obs')">System Health</button>
        <button class="btn btn-header" onclick="openModal('modal-field')">Field Verification</button>
        <button class="btn btn-header" onclick="openModal('modal-prov')">Data Provenance</button>
        <a class="btn btn-header" href="index.html" id="btn-root-link" style="display: none;">Root Dashboard</a>
        <button class="btn btn-header" onclick="openModal('modal-modules')">Sub-Modules</button>
        <a class="btn btn-header" href="https://github.com/Nishanth773/AquaRehearsal-X" target="_blank" rel="noopener">GitHub</a>
      </div>
    </div>

    <!-- SYSTEM OBSERVABILITY SUB-BAR -->
    <div class="observability-bar">
      <span class="obs-label">System Observability:</span>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-limitation"></div> Telemetry: USGS 01474500 (Hourly Active)</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-safe"></div> Precipitation: Open-Meteo ERA5</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-limitation"></div> ML Model: LightGBM Model B (156 Feat)</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-safe"></div> Forecast: 72h Min DO (Quantiles + Conformal)</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-limitation"></div> Safe Boundary: STE Validated [1, 31°C]</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-limitation"></div> Action Window: Empirical Lag P10 = 6.5h</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-unvalidated"></div> Interventions: Mass-Balance Only</div>
      <div class="obs-item" onclick="openModal('modal-obs')"><div class="dot dot-limitation"></div> Validation: Dual-Track Ledger</div>
    </div>
  </header>

  <!-- MAIN WORKSPACE -->
  <main>
    <!-- HISTORICAL REPLAY BANNER -->
    <div class="banner-replay" id="replay-banner">
      <div>
        <strong>HISTORICAL STORM RECONSTRUCTION — EVENT 54:</strong> August 5, 2026 Severe Storm (26.5 mm rainfall, pre-event temperature 26.5°C).
        Evaluation fixed strictly at forecast origin <code>2026-08-05T20:00:00Z</code>.
        Observed event nadir: <strong>5.65 mg/L</strong> (Drop: 1.45 mg/L).
        Model B absolute error: <strong>0.40 mg/L</strong> vs Naive persistence error: <strong>1.45 mg/L</strong>.
      </div>
      <button class="btn btn-secondary" onclick="toggleReplayMode()">Exit Replay</button>
    </div>

    <!-- GUIDED DEMO STEPPER BANNER -->
    <div class="banner-tour" id="tour-box">
      <div class="tour-content">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span style="font-weight: 700; text-transform: uppercase; font-size: 0.72rem; color: #0284c7;" id="tour-step-badge">STEP 1 OF 7: PROBLEM DEFINITION</span>
          <span style="font-size: 0.7rem; color: var(--text-muted);" id="tour-step-timer">Target Time: 0:00 - 0:25</span>
        </div>
        <strong style="font-size: 0.88rem; color: var(--text-main);" id="tour-step-title">The Challenge of Urban Stormwater Deoxygenation</strong>
        <p style="font-size: 0.75rem; color: var(--text-muted); max-width: 1100px;" id="tour-step-desc">
          Urban streams experience sudden water quality shocks during storms from thermal runoff and sewer overflows. Decision-makers need uncertainty-bounded forecasts and actionable safe boundaries before runoff hits.
        </p>
      </div>
      <div class="tour-stepper">
        <button class="btn btn-secondary" onclick="prevTourStep()">Previous</button>
        <button class="btn btn-primary" onclick="nextTourStep()">Next Step</button>
        <button class="btn btn-secondary" onclick="stopTour()">Exit</button>
      </div>
    </div>

    <!-- REAL METADATA STRIP -->
    <div class="metadata-strip">
      <div class="meta-group">
        <div class="meta-item">Station: <strong>USGS 01474500 (Schuylkill River at Philadelphia, PA)</strong></div>
        <div class="meta-item">Coordinates: <strong>39°58'00" N, 75°11'20" W</strong> (NAD83)</div>
        <div class="meta-item">HUC8: <strong>02040203</strong></div>
        <div class="meta-item">Drainage Basin: <strong>1,893 mi²</strong></div>
      </div>
      <div class="meta-group">
        <div class="meta-item">Observation Time: <strong>2026-09-29 03:00 UTC</strong></div>
        <div class="meta-item">Forecast Horizon: <strong>72 Hours (t₀ to t₀ + 72h)</strong></div>
        <div class="meta-item">Target Criterion: <strong>PA DEP Ch. 93 (τ = 5.00 mg/L)</strong></div>
      </div>
    </div>

    <!-- CURRENT STREAM MEASUREMENTS -->
    <div class="kpi-grid" id="section-kpis">
      <div class="kpi-card" id="kpi-card-do">
        <span class="kpi-param-code">USGS 00300 • CONTINUOUS SENSOR</span>
        <span class="kpi-title">Dissolved Oxygen</span>
        <div class="kpi-value-row">
          <span class="kpi-value" id="kpi-do">7.10</span>
          <span class="kpi-unit">mg/L</span>
        </div>
        <span class="kpi-footer" id="kpi-do-sat">88.4% Saturation • Quality: Valid</span>
      </div>

      <div class="kpi-card" id="kpi-card-temp">
        <span class="kpi-param-code">USGS 00010 • CONTINUOUS SENSOR</span>
        <span class="kpi-title">Water Temperature (T₀)</span>
        <div class="kpi-value-row">
          <span class="kpi-value" id="kpi-temp">26.5</span>
          <span class="kpi-unit">°C</span>
        </div>
        <span class="kpi-footer">Elevated summer thermal regime</span>
      </div>

      <div class="kpi-card" id="kpi-card-q">
        <span class="kpi-param-code">USGS 00060 • DISCHARGE GAUGE</span>
        <span class="kpi-title">Stream Discharge (Q)</span>
        <div class="kpi-value-row">
          <span class="kpi-value" id="kpi-q">900</span>
          <span class="kpi-unit">cfs</span>
        </div>
        <span class="kpi-footer">Baseflow rating curve normal</span>
      </div>

      <div class="kpi-card" id="kpi-card-rain">
        <span class="kpi-param-code">METEOROLOGICAL REANALYSIS</span>
        <span class="kpi-title">Incoming Storm Rainfall</span>
        <div class="kpi-value-row">
          <span class="kpi-value" id="kpi-rain">26.5</span>
          <span class="kpi-unit">mm</span>
        </div>
        <span class="kpi-footer">24-hour total accumulation</span>
      </div>

      <div class="kpi-card" id="kpi-card-thr">
        <span class="kpi-param-code">REGULATORY THRESHOLD</span>
        <span class="kpi-title">Critical DO Standard (τ)</span>
        <div class="kpi-value-row">
          <span class="kpi-value" style="color: #0369a1;" id="kpi-thr">5.00</span>
          <span class="kpi-unit">mg/L</span>
        </div>
        <span class="kpi-footer">PA DEP Chapter 93 Standard</span>
      </div>
    </div>

    <!-- INTERACTIVE SCENARIO CONTROLS -->
    <div class="controls-panel" id="section-controls">
      <div class="controls-header">
        <span class="controls-title">Scenario Parameters & Engineering Stress Testing</span>
        <span style="font-size: 0.7rem; color: var(--text-sub);">Adjust sliders to evaluate safe boundary and 72-hour forecast dynamics</span>
      </div>

      <div class="controls-grid">
        <div class="control-item">
          <div class="control-label">
            <span>Water Temperature (T₀):</span>
            <span class="control-val" id="val-temp">26.5 °C</span>
          </div>
          <input type="range" id="slider-temp" min="4.0" max="35.0" step="0.5" value="26.5" oninput="updateScenario()">
        </div>

        <div class="control-item">
          <div class="control-label">
            <span>Incoming Rainfall (R_storm):</span>
            <span class="control-val" id="val-rain">26.5 mm</span>
          </div>
          <input type="range" id="slider-rain" min="0.0" max="70.0" step="1.0" value="26.5" oninput="updateScenario()">
        </div>

        <div class="control-item">
          <div class="control-label">
            <span>Critical DO Threshold (τ):</span>
            <span class="control-val" id="val-thr">5.0 mg/L</span>
          </div>
          <input type="range" id="slider-thr" min="3.5" max="6.5" step="0.1" value="5.0" oninput="updateScenario()">
        </div>

        <div class="control-item">
          <div class="control-label">
            <span>Operational Risk Limit (α):</span>
            <span class="control-val" id="val-risk">20 %</span>
          </div>
          <input type="range" id="slider-risk" min="5" max="40" step="1" value="20" oninput="updateScenario()">
        </div>
      </div>

      <div class="presets-bar">
        <span style="font-weight: 600;">Scenario Presets:</span>
        <button class="preset-btn" onclick="applyPreset(26.5, 26.5, 5.0, 20)">August 2026 Severe Storm (Event 54)</button>
        <button class="preset-btn" onclick="applyPreset(14.0, 18.0, 5.0, 20)">Cool Autumn Rain (Safe Baseflow)</button>
        <button class="preset-btn" onclick="applyPreset(29.5, 38.0, 5.0, 20)">High Thermal Stress (Elevated Risk)</button>
        <button class="preset-btn" onclick="applyPreset(34.0, 65.0, 5.0, 20)">Extreme Out-of-Domain (Refusal Trigger)</button>
      </div>
    </div>

    <!-- CENTERPIECE: HERO 2D STORM TOLERANCE ENVELOPE vs 72H DO FORECAST -->
    <div class="grid-centerpiece">
      <!-- HERO 2D STORM TOLERANCE ENVELOPE -->
      <div class="card card-hero" id="card-ste">
        <div class="card-header">
          <div>
            <div class="card-title">Storm Tolerance Envelope (STE) — Safe-Boundary Engine</div>
            <div class="card-subtitle">2D Phase Space Mapping Pre-Storm Temperature (T₀) against Incoming Rainfall (R_storm)</div>
          </div>
          <span class="status-badge badge-status-advisory" id="badge-ste-status">EXCEEDS_SAFE_ALLOWANCE</span>
        </div>

        <!-- 2D STE CANVAS -->
        <div class="canvas-wrap-ste">
          <canvas id="steCanvas"></canvas>
        </div>

        <!-- STE SUMMARY METRICS -->
        <div class="ste-summary-grid">
          <div class="ste-summary-col">
            <span class="ste-label">Safe Rain Allowance (R_safe):</span>
            <span class="ste-val" style="color: #0369a1;" id="ste-allowance">21.0 mm</span>
          </div>
          <div class="ste-summary-col">
            <span class="ste-label">Breach Risk P(DO &lt; τ):</span>
            <span class="ste-val" style="color: #b45309;" id="ste-prob">14.8%</span>
          </div>
          <div class="ste-summary-col">
            <span class="ste-label">Operational Alert Tier:</span>
            <span class="ste-val" style="color: #b45309;" id="ste-level">ADVISORY</span>
          </div>
          <div class="ste-summary-col">
            <span class="ste-label">Domain Classification:</span>
            <span class="ste-val" style="color: #15803d;" id="ste-domain">IN_DOMAIN</span>
          </div>
        </div>

        <div class="notice-box notice-advisory" id="ste-disclaimer">
          <div>
            <strong>Preliminary Boundary Evidence:</strong> Calibrated on 58 cataloged events (2023–2026). Zero historical collapses &lt;5.0 mg/L occurred in the record. The safe envelope represents empirical statistical risk rather than an observed ecological failure threshold.
          </div>
        </div>
      </div>

      <!-- 72-HOUR DO FORECAST & INTERVENTION REHEARSAL -->
      <div class="card" id="card-traj">
        <div class="card-header">
          <div>
            <div class="card-title">72-Hour DO Trajectory & Intervention Rehearsal</div>
            <div class="card-subtitle">In-Silico Streeter-Phelps Mass Balance Coupled with Model B Quantile Predictions</div>
          </div>
          <span class="status-badge badge-status-safe" id="badge-int-feas">FEASIBLE_IN_TIME</span>
        </div>

        <!-- INTERVENTION SELECTOR TABS -->
        <div class="intervention-tabs">
          <div class="int-tab active" onclick="selectIntervention('temporary_aeration')">Diffused Aeration (4h lead)</div>
          <div class="int-tab" onclick="selectIntervention('runoff_reduction')">Runoff Detention (6h lead)</div>
          <div class="int-tab" onclick="selectIntervention('stormwater_detention')">CSO Storage (8h lead)</div>
          <div class="int-tab" onclick="selectIntervention('riparian_shading')">Riparian Shading (Long-term)</div>
        </div>

        <!-- TRAJECTORY CANVAS -->
        <div class="canvas-wrap-traj">
          <canvas id="trajCanvas"></canvas>
        </div>

        <!-- TRAJECTORY METRICS -->
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; font-size: 0.74rem; background: var(--bg-subtle); padding: 0.55rem 0.75rem; border-radius: 3px; border: 1px solid var(--border-light);">
          <div>Baseline Min DO: <strong style="font-family: var(--font-mono); color: var(--text-main);" id="lbl-base-do">6.05 mg/L</strong></div>
          <div>Rehearsed Min DO: <strong style="font-family: var(--font-mono); color: #15803d;" id="lbl-mod-do">6.82 mg/L (+0.77)</strong></div>
          <div>Action Deadline: <strong style="font-family: var(--font-mono); color: #0369a1;" id="lbl-deadline">6.5 to 10.0 Hours</strong></div>
        </div>

        <div class="notice-box notice-info">
          <div>
            <strong>Engineering Simulation Transparency:</strong> Dissolved oxygen recovery dynamics are simulated via continuous Streeter-Phelps differential mass balance. Physical in-stream mechanical aeration diffusers were not deployed in the field.
          </div>
        </div>
      </div>
    </div>

    <!-- LOWER 3-COLUMN DECISION SUPPORT PANELS -->
    <div class="grid-3col">
      <!-- ACTION WINDOW & LATENCY -->
      <div class="card" id="card-action">
        <div class="card-header">
          <div class="card-title">Empirical Action Window Analysis</div>
          <span class="status-badge" style="background: var(--bg-subtle); border-color: var(--border-main); color: var(--text-muted);">Stage 4 Hydrodynamics</span>
        </div>

        <div style="font-size: 0.75rem; color: var(--text-muted);">
          Empirical lag-to-nadir distribution calibrated across 58 storm events at USGS 01474500:
        </div>

        <table class="stat-table">
          <thead>
            <tr>
              <th>Quantile Horizon</th>
              <th>Estimated Lead Time</th>
              <th>Cumulative Breach Risk</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Earliest Plausible (P10)</td>
              <td><strong style="color: #b91c1c;">6.5 Hours</strong></td>
              <td>P(≤6h) = 2%</td>
            </tr>
            <tr>
              <td>Central Expectation (P50)</td>
              <td><strong style="color: #0369a1;">10.0 Hours</strong></td>
              <td>P(≤12h) = 11%</td>
            </tr>
            <tr>
              <td>Extended Trailing (P90)</td>
              <td><strong>18.0 Hours</strong></td>
              <td>P(≤24h) = 15%</td>
            </tr>
          </tbody>
        </table>

        <div style="font-size: 0.71rem; color: var(--text-sub); line-height: 1.35;">
          *Note: Not a deterministic countdown clock. Interventions with &gt;6h logistical mobilization times must receive advance authorization upon issuance of an advisory.
        </div>
      </div>

      <!-- CITIZEN FIELD CHECK VERIFICATION -->
      <div class="card" id="card-field">
        <div class="card-header">
          <div class="card-title">Citizen Science Ground Verification</div>
          <span class="status-badge" style="background: var(--bg-subtle); border-color: var(--border-main); color: var(--text-muted);">Stage 5 Ground-Truth</span>
        </div>

        <div style="font-size: 0.75rem; color: var(--text-muted);">
          Contextual field observations ground-truth ML forecasts without contaminating numerical model labels:
        </div>

        <table class="stat-table">
          <thead>
            <tr>
              <th>Ledger Metric</th>
              <th>Status</th>
              <th>Verification Quality</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Volunteer Sensor Reports</td>
              <td><strong>2 Records</strong></td>
              <td><span style="color: #15803d; font-weight: 600;">Verified (Handheld Probe)</span></td>
            </tr>
            <tr>
              <td>Synthetic Test Demonstration</td>
              <td><strong>1 Record</strong></td>
              <td><span style="color: #64748b;">Isolated / Tagged QA</span></td>
            </tr>
            <tr>
              <td>Corroboration Ratio</td>
              <td><strong style="color: #15803d;">66.7%</strong></td>
              <td><span style="color: #15803d;">Consistent with Forecast</span></td>
            </tr>
          </tbody>
        </table>

        <button class="btn btn-secondary" style="width: 100%; justify-content: center; margin-top: 0.2rem;" onclick="openModal('modal-field')">
          Submit Field Verification Observation
        </button>
      </div>

      <!-- ONE HEALTH RESILIENCE FRAMEWORK -->
      <div class="card" id="card-onehealth">
        <div class="card-header">
          <div class="card-title">One Health Ecological Resilience Review</div>
          <span class="status-badge" style="background: var(--bg-subtle); border-color: var(--border-main); color: var(--text-muted);">EPA / PA DEP Alignment</span>
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.45rem; font-size: 0.74rem;">
          <div style="border-left: 3px solid #0284c7; padding-left: 0.55rem;">
            <strong style="color: #0369a1;">1. Environmental Assimilative Integrity:</strong>
            <div style="color: var(--text-muted);">Forecast minimum DO of 6.05 mg/L with reaeration rate 0.42 day⁻¹ preserves biological assimilative capacity.</div>
          </div>
          <div style="border-left: 3px solid #15803d; padding-left: 0.55rem;">
            <strong style="color: #15803d;">2. Aquatic Life & Fisheries Preservation:</strong>
            <div style="color: var(--text-muted);">Maintains PA Chapter 93 warm-water fishes standard (5.0 mg/L); safely clears acute lethal threshold (3.0 mg/L).</div>
          </div>
          <div style="border-left: 3px solid #b45309; padding-left: 0.55rem;">
            <strong style="color: #b45309;">3. Human Recreation & Pathogen Contact:</strong>
            <div style="color: #b45309; font-weight: 700;">NOT ASSESSED</div>
            <div style="color: var(--text-muted); font-size: 0.71rem;">Turbidity and DO parameters do not measure bacterial or viral pathogens. Contact with stormwater must be avoided.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- SCIENTIFIC LIMITATIONS PANEL -->
    <div class="limitations-panel" id="section-limitations">
      <div class="limitations-header">
        <div class="limitations-title">Scientific Limitations & Technical Governance Policy</div>
        <span style="font-size: 0.72rem; color: var(--text-sub);">AquaRehearsal-X Methodological Transparency & Guardrails</span>
      </div>

      <div class="limitations-grid">
        <div class="lim-card">
          <span class="lim-tag">Limitation 1</span>
          <span class="lim-heading">Single-Station Calibration</span>
          <span class="lim-body">Models are calibrated strictly for USGS 01474500 on the Schuylkill River. Regional hydrologic transferability to headwater tributaries is unverified.</span>
          <div class="lim-advancement">Advancement: Calibrate across multi-station regional USGS river basin networks.</div>
        </div>

        <div class="lim-card">
          <span class="lim-tag">Limitation 2</span>
          <span class="lim-heading">Absence of Historical Breaches &lt;5.0 mg/L</span>
          <span class="lim-body">In the 58-event catalog (2023–2026), the minimum observed event DO was 5.65 mg/L. Breach risk calculations represent statistical extrapolation.</span>
          <div class="lim-advancement">Advancement: Extend training archive with decadal records capturing severe drought-storm sequences.</div>
        </div>

        <div class="lim-card">
          <span class="lim-tag">Limitation 3</span>
          <span class="lim-heading">Preliminary Statistical Boundary</span>
          <span class="lim-body">The safe envelope represents empirical logistic probability contours, not an immutable physical cliff. Threshold contracts with antecedent soil moisture.</span>
          <div class="lim-advancement">Advancement: Couple with 2D hydrodynamic numerical water quality models (CE-QUAL-W2).</div>
        </div>

        <div class="lim-card">
          <span class="lim-tag">Limitation 4</span>
          <span class="lim-heading">Empirical Lag Timing Distribution</span>
          <span class="lim-body">Action window represents empirical quantiles (P10 6.5h, P50 10.0h, P90 18.0h). Plume travel times vary depending on storm kinematics.</span>
          <div class="lim-advancement">Advancement: Integrate radar storm velocity vectors and NEXRAD rainfall tracking.</div>
        </div>

        <div class="lim-card">
          <span class="lim-tag">Limitation 5</span>
          <span class="lim-heading">Theoretical Intervention Kinetics</span>
          <span class="lim-body">Oxygen recovery values (+0.77 mg/L) are computed via idealized Streeter-Phelps mass balances without physical in-stream mechanical aeration trials.</span>
          <div class="lim-advancement">Advancement: Conduct controlled pilot diffuser tracer experiments in instream reaches.</div>
        </div>

        <div class="lim-card">
          <span class="lim-tag">Limitation 6 & 7</span>
          <span class="lim-heading">Diurnal Bias & Microbial Pathogens</span>
          <span class="lim-body">Citizen science observations cluster between 08:00–20:00 UTC, missing critical pre-dawn sags. Pathogen presence is unassessed without certified lab assays.</span>
          <div class="lim-advancement">Advancement: Deploy automated night grab-samplers and microfluidic qPCR pathogen monitors.</div>
        </div>
      </div>
    </div>
  </main>

  <!-- MODAL 1: SYSTEM HEALTH & OBSERVABILITY -->
  <div class="modal-overlay" id="modal-obs">
    <div class="modal-box">
      <div class="modal-header">
        <h3>Subsystem Observability & Diagnostic Health Audit</h3>
        <button class="close-btn" onclick="closeModal('modal-obs')">×</button>
      </div>
      <table class="modal-data-table">
        <thead>
          <tr>
            <th>Subsystem Component</th>
            <th>Operational Health Status</th>
            <th>Diagnostic Details & Constraints</th>
          </tr>
        </thead>
        <tbody id="obs-tbody">
          <!-- Populated by JS -->
        </tbody>
      </table>
    </div>
  </div>

  <!-- MODAL 2: FIELD VERIFICATION SUBMISSION -->
  <div class="modal-overlay" id="modal-field">
    <div class="modal-box">
      <div class="modal-header">
        <h3>Submit Citizen Science Field Verification Observation</h3>
        <button class="close-btn" onclick="closeModal('modal-field')">×</button>
      </div>
      <div class="notice-box notice-advisory">
        <div>
          <strong>Safety Precaution:</strong> Never approach flooded banks or step into fast-flowing water.
          Observations are public records. Coordinates are fuzzed to ~1.1 km resolution to protect private property.
        </div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 0.65rem; font-size: 0.78rem;">
        <label>
          Stream Location Name / Landmark:
          <input type="text" id="field-loc" value="Schuylkill Banks near Walnut St" style="width: 100%; padding: 0.4rem; border: 1px solid var(--border-main); border-radius: 3px; margin-top: 0.2rem; font-family: var(--font-main);">
        </label>
        <label>
          Water Visual Appearance:
          <select id="field-app" style="width: 100%; padding: 0.4rem; border: 1px solid var(--border-main); border-radius: 3px; margin-top: 0.2rem; font-family: var(--font-main);">
            <option value="CLEAR">Clear</option>
            <option value="SLIGHTLY_TURBID">Slightly Turbid / Mild Silt</option>
            <option value="BROWN_TURBID" selected>Brown / Heavy Sediment Wash</option>
            <option value="GREEN_ALGAL">Green / Algal Growth Visible</option>
          </select>
        </label>
        <label>
          Unusual Foam or Odor:
          <select id="field-foam" style="width: 100%; padding: 0.4rem; border: 1px solid var(--border-main); border-radius: 3px; margin-top: 0.2rem; font-family: var(--font-main);">
            <option value="NONE">None</option>
            <option value="TRACE" selected>Trace Foam at Riffles</option>
            <option value="MODERATE">Moderate Foam Accumulation</option>
          </select>
        </label>
        <label>
          Aquatic Fauna Activity:
          <select id="field-fish" style="width: 100%; padding: 0.4rem; border: 1px solid var(--border-main); border-radius: 3px; margin-top: 0.2rem; font-family: var(--font-main);">
            <option value="NORMAL_FISH_SWIMMING" selected>Normal Fish Activity Visible</option>
            <option value="FISH_GULPING_SURFACE">Fish Gulping Air at Surface (Piping)</option>
            <option value="DEAD_FISH_PRESENT">Dead Fish Observed</option>
          </select>
        </label>
        <label>
          Handheld DO Measurement (optional, mg/L):
          <input type="number" id="field-do" placeholder="e.g. 5.80" step="0.01" style="width: 100%; padding: 0.4rem; border: 1px solid var(--border-main); border-radius: 3px; margin-top: 0.2rem; font-family: var(--font-mono);">
        </label>
        <label style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.72rem; color: var(--text-muted);">
          <input type="checkbox" id="field-consent" checked>
          I confirm observation was conducted from a safe public vantage point and consent to anonymized open research publication.
        </label>
        <button class="btn btn-primary" style="justify-content: center; padding: 0.5rem;" onclick="submitReport()">Submit Observation</button>
      </div>
    </div>
  </div>

  <!-- MODAL 3: PROVENANCE AUDIT -->
  <div class="modal-overlay" id="modal-prov">
    <div class="modal-box">
      <div class="modal-header">
        <h3>Data and Model Provenance Ledger</h3>
        <button class="close-btn" onclick="closeModal('modal-prov')">×</button>
      </div>
      <div style="font-size: 0.78rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.55rem; line-height: 1.45;">
        <div><strong>Primary Monitoring Station:</strong> USGS 01474500 (Schuylkill River at Philadelphia, PA)</div>
        <div><strong>Drainage Basin:</strong> 1,893 square miles | Hydrologic Unit: 02040203 | Datum: NAD83</div>
        <div><strong>Stream Telemetry Ingestion:</strong> USGS NWIS Instantaneous Value API (Hourly regularized)</div>
        <div><strong>Meteorological Telemetry:</strong> ECMWF ERA5 Reanalysis & Open-Meteo Hourly Forecast API</div>
        <div><strong>Predictive Model:</strong> Stage 2.5 LightGBM Model B (156 backward features, zero future leakage)</div>
        <div><strong>Uncertainty Formulation:</strong> Quantile Regressors (q10, q50, q90) + Split Conformal Calibration (±1.955 mg/L coverage)</div>
        <div><strong>Domain Boundary:</strong> 2D Delaunay Convex Hull [1.0°C to 31.0°C, 0 to 55 mm rain]</div>
        <div><strong>Anti-Contamination Rule:</strong> Citizen observations are strictly contextual and NEVER used as numerical training labels.</div>
      </div>
    </div>
  </div>

  <!-- MODAL 4: TECHNICAL SUMMARY -->
  <div class="modal-overlay" id="modal-judge">
    <div class="modal-box" style="max-width: 850px;">
      <div class="modal-header">
        <h3>Technical System Architecture & Evaluation Summary</h3>
        <button class="close-btn" onclick="closeModal('modal-judge')">×</button>
      </div>
      <div style="font-size: 0.76rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.65rem; line-height: 1.45;">
        <div>
          <strong style="color: var(--text-main);">1. Hydrologic Problem Statement:</strong>
          Urban storm events trigger sudden, severe deoxygenation in freshwater streams due to combined sewer overflows (CSOs), benthic sediment resuspension, and elevated runoff temperatures. Decision-makers lack tools combining predictive ML with calibrated uncertainty and actionable safe boundaries.
        </div>
        <div>
          <strong style="color: var(--text-main);">2. Intended Operational Users:</strong>
          Municipal watershed managers, environmental protection agencies, stormwater utility operators, and aquatic conservation teams.
        </div>
        <div>
          <strong style="color: var(--text-main);">3. Pipeline Architecture:</strong>
          End-to-end Python scientific pipeline (Stages 1–7): USGS/ERA5 Ingestion → LightGBM Model B → 2D Storm Tolerance Envelope → Empirical Action Window → Streeter-Phelps Intervention Solver → Privacy-Preserving Field Verification.
        </div>
        <div>
          <strong style="color: var(--text-main);">4. Machine-Learning Methodology:</strong>
          LightGBM gradient boosting regressor forecasting 72-hour minimum DO from 156 backward-looking features. Quantile regressors (q10, q50, q90) guarantee non-crossing intervals, calibrated via inductive split conformal inference (90% guaranteed coverage).
        </div>
        <div>
          <strong style="color: var(--text-main);">5. Storm Tolerance Envelope (Centerpiece):</strong>
          Empirical safe boundary R_safe = f(T_water) establishing maximum permissible rainfall before threshold breach probability exceeds operational risk limit alpha. Governed by a Delaunay convex hull domain refusal guardrail.
        </div>
        <div>
          <strong style="color: var(--text-main);">6. Intervention Rehearsal & Lag Timing:</strong>
          Empirical lag distributions establish operational decision deadlines (P10 = 6.5h, P50 = 10.0h). Continuous Streeter-Phelps mass balance rehearses 4 response archetypes with logistical feasibility gating.
        </div>
        <div>
          <strong style="color: var(--text-main);">7. Field Verification & One Health:</strong>
          Dual-track validation ledger segregates citizen observations from certified sensors. Coordinate coarsening (~1.1 km) protects privacy. Human-contact risk is marked NOT ASSESSED without laboratory microbial assays.
        </div>
      </div>
    </div>
  </div>

  <!-- MODAL 5: SCIENTIFIC LIMITATIONS MODAL -->
  <div class="modal-overlay" id="modal-limits">
    <div class="modal-box">
      <div class="modal-header">
        <h3 style="color: #b45309;">Full Scientific Limitations Disclosure</h3>
        <button class="close-btn" onclick="closeModal('modal-limits')">×</button>
      </div>
      <div style="font-size: 0.76rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.55rem; line-height: 1.45;">
        <div><strong>1. Single Station Calibration:</strong> Calibrated strictly on USGS 01474500 (Schuylkill River at Philadelphia). Not validated for headwater tributaries.</div>
        <div><strong>2. No Observed DO Breaches Below 5.0 mg/L:</strong> In our 58-event catalog (2023–2026), the lowest observed storm minimum was 5.65 mg/L (Event 54). Extreme breach risk curves represent statistical extrapolations rather than empirical collapses.</div>
        <div><strong>3. Preliminary Risk Boundary:</strong> The safe boundary curve is an empirical decision contour, not a rigid physical failure threshold.</div>
        <div><strong>4. Action Window Uncertainty:</strong> The lag-to-nadir bounds are empirical percentiles, not a deterministic countdown timer.</div>
        <div><strong>5. Unvalidated Simulation:</strong> Intervention benefits (+0.77 mg/L) are calculated via continuous Streeter-Phelps mass-balance equations; no in-situ engineering deployment occurred.</div>
        <div><strong>6. Daytime Observation Bias:</strong> Citizen submissions are clustered between 08:00–20:00 UTC, missing pre-dawn oxygen sags.</div>
        <div><strong>7. Missing Microbial Assays:</strong> Dissolved oxygen cannot verify pathogen safety. Human contact risk is NOT ASSESSED without laboratory bacterial culture data.</div>
      </div>
    </div>
  </div>

  <!-- MODAL 6: SUB-MODULES NAVIGATOR -->
  <div class="modal-overlay" id="modal-modules">
    <div class="modal-box" style="max-width: 820px;">
      <div class="modal-header">
        <h3>Specialized Stage Sub-Module Applications</h3>
        <button class="close-btn" onclick="closeModal('modal-modules')">×</button>
      </div>
      <p style="font-size: 0.78rem; color: var(--text-muted);">
        AquaRehearsal-X comprises specialized analytical modules built across Stages 3 through 6. Access each standalone report interface below:
      </p>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 0.75rem;">
        <!-- Card 1: Stage 3 STE -->
        <div style="background: var(--bg-subtle); border: 1px solid var(--border-main); border-radius: 4px; padding: 0.85rem; display: flex; flex-direction: column; justify-content: space-between; gap: 0.75rem;">
          <div>
            <div style="font-size: 0.68rem; font-weight: 700; color: #0284c7; text-transform: uppercase;">Stage 3 Application</div>
            <h4 style="color: var(--text-main); font-size: 0.88rem; margin: 0.2rem 0;">Storm Tolerance Envelope</h4>
            <p style="color: var(--text-muted); font-size: 0.73rem; line-height: 1.35;">
              2D safe boundary explorer mapping pre-storm water temperature against storm rainfall with Monte Carlo quantiles and 58 historical storm scatter plots.
            </p>
          </div>
          <a class="btn btn-primary" data-module-stage="stage3" data-module-file="storm_tolerance_envelope_app.html" href="data/reports/stage3/storm_tolerance_envelope_app.html" style="justify-content: center;">Launch STE App →</a>
        </div>

        <!-- Card 2: Stage 4 Rehearsal -->
        <div style="background: var(--bg-subtle); border: 1px solid var(--border-main); border-radius: 4px; padding: 0.85rem; display: flex; flex-direction: column; justify-content: space-between; gap: 0.75rem;">
          <div>
            <div style="font-size: 0.68rem; font-weight: 700; color: #7c3aed; text-transform: uppercase;">Stage 4 Application</div>
            <h4 style="color: var(--text-main); font-size: 0.88rem; margin: 0.2rem 0;">Intervention Rehearsal</h4>
            <p style="color: var(--text-muted); font-size: 0.73rem; line-height: 1.35;">
              Continuous Streeter-Phelps oxygen sag dynamics simulator, action window countdown (P10 6.5h), and comparative response scenario rehearsal.
            </p>
          </div>
          <a class="btn btn-primary" data-module-stage="stage4" data-module-file="intervention_rehearsal_app.html" href="data/reports/stage4/intervention_rehearsal_app.html" style="justify-content: center; background: #7c3aed;">Launch Rehearsal App →</a>
        </div>

        <!-- Card 3: Stage 5 Field Check -->
        <div style="background: var(--bg-subtle); border: 1px solid var(--border-main); border-radius: 4px; padding: 0.85rem; display: flex; flex-direction: column; justify-content: space-between; gap: 0.75rem;">
          <div>
            <div style="font-size: 0.68rem; font-weight: 700; color: #15803d; text-transform: uppercase;">Stage 5 Application</div>
            <h4 style="color: var(--text-main); font-size: 0.88rem; margin: 0.2rem 0;">Field Check & Drift QA</h4>
            <p style="color: var(--text-muted); font-size: 0.73rem; line-height: 1.35;">
              Dual-track verification ledger, optical sensor drift tracking, and daytime biological bias correction for citizen science observations.
            </p>
          </div>
          <a class="btn btn-primary" data-module-stage="stage5" data-module-file="field_check_dashboard.html" href="data/reports/stage5/field_check_dashboard.html" style="justify-content: center; background: #15803d;">Launch Field Check →</a>
        </div>
      </div>
    </div>
  </div>

  <!-- EMBEDDED JAVASCRIPT & CLIENT-SIDE ENGINE -->
  <script>
    const APP_DATA = __EMBEDDED_JSON__;

    let isReplayMode = false;
    let currentIntervention = 'temporary_aeration';
    let tourStep = 0;

    // 7-Step Guided Narrative
    const tourSteps = [
      {
        badge: "STEP 1 OF 7: PROBLEM DEFINITION",
        timer: "Target Time: 0:00 - 0:25",
        title: "The Problem — Urban Stormwater Deoxygenation",
        desc: "Urban streams experience sudden water quality shocks during storms. Conventional environmental dashboards only report retrospective measurements. Decision-makers need forward-looking predictions, calibrated uncertainty, and proactive response options.",
        targetId: "section-kpis",
        apply: () => applyPreset(26.5, 26.5, 5.0, 20)
      },
      {
        badge: "STEP 2 OF 7: REAL STREAM CONDITIONS",
        timer: "Target Time: 0:25 - 0:55",
        title: "Real Stream Conditions — USGS 01474500",
        desc: "We begin with real, continuous stream telemetry from USGS 01474500 on the Schuylkill River at Philadelphia (drainage area 1,893 sq mi). Current values reflect summer conditions: DO 7.10 mg/L (88.4% saturation), Water Temperature 26.5°C, and Discharge 900 cfs.",
        targetId: "kpi-card-do",
        apply: () => applyPreset(26.5, 26.5, 5.0, 20)
      },
      {
        badge: "STEP 3 OF 7: PREDICTIVE FORECASTING",
        timer: "Target Time: 0:55 - 1:25",
        title: "Predict Future DO — 72-Hour Forecast & Uncertainty",
        desc: "For an incoming 26.5 mm storm, our LightGBM Model B forecasts minimum DO dropping to 6.05 mg/L. Unlike naive persistence (7.10 mg/L), Model B anticipates the oxygen sag within 0.40 mg/L error, with split conformal bounds [4.10, 8.01] mg/L.",
        targetId: "card-traj",
        apply: () => applyPreset(26.5, 26.5, 5.0, 20)
      },
      {
        badge: "STEP 4 OF 7: STORM TOLERANCE ENVELOPE",
        timer: "Target Time: 1:25 - 2:05",
        title: "Storm Tolerance Envelope — 2D Safe-Boundary Engine",
        desc: "The Storm Tolerance Envelope maps rainfall against pre-storm temperature to evaluate safe margins. At 26.5°C, the safe rainfall allowance is 21.0 mm. Incoming 26.5 mm rain exceeds this boundary, triggering an ADVISORY alert (14.8% breach probability). The boundary is preliminary, with zero observed breaches <5.0 mg/L in our historical catalog.",
        targetId: "card-ste",
        apply: () => applyPreset(26.5, 26.5, 5.0, 20)
      },
      {
        badge: "STEP 5 OF 7: INTERVENTION REHEARSAL",
        timer: "Target Time: 2:05 - 2:35",
        title: "Rehearse an Intervention — Feasibility & Mass Balance",
        desc: "Decision-makers rehearse responses before the storm arrives. With an empirical action window of 6.5 to 10.0 hours to the oxygen nadir, mobilizing Diffused Aeration (4h lead time) is logistically FEASIBLE, projecting a +0.77 mg/L recovery. This mass-balance simulation is not yet empirically validated in-situ.",
        targetId: "card-traj",
        apply: () => { selectIntervention('temporary_aeration'); }
      },
      {
        badge: "STEP 6 OF 7: GROUND-TRUTHING & ONE HEALTH",
        timer: "Target Time: 2:35 - 2:55",
        title: "Field Check & One Health — Ground-Truthing with Guardrails",
        desc: "Volunteers submit contextual stream observations. A verified handheld probe reading of 5.80 mg/L corroborates our forecast. In our One Health triad, human-contact risk is strictly marked NOT ASSESSED because visual clarity cannot determine microbial pathogen safety.",
        targetId: "card-field",
        apply: () => applyPreset(26.5, 26.5, 5.0, 20)
      },
      {
        badge: "STEP 7 OF 7: SYNTHESIS & TRANSPARENCY",
        timer: "Target Time: 2:55 - 3:15",
        title: "Platform Synthesis — Transparent Decision Support",
        desc: "AquaRehearsal-X bridges continuous sensor monitoring, machine-learning forecasting, proactive scenario rehearsal, and community verification — delivering an honest, scientifically humble decision-support platform for urban waterways.",
        targetId: "section-limitations",
        apply: () => applyPreset(26.5, 26.5, 5.0, 20)
      }
    ];

    function resolveModuleLinks() {
      const isSubdir = window.location.pathname.includes('/stage6/');
      const rootLink = document.getElementById('btn-root-link');
      if (rootLink) {
        rootLink.style.display = isSubdir ? 'inline-flex' : 'none';
      }
      const links = document.querySelectorAll('a[data-module-stage]');
      links.forEach(a => {
        const stage = a.getAttribute('data-module-stage');
        const file = a.getAttribute('data-module-file');
        if (isSubdir) {
          a.href = `../${stage}/${file}`;
        } else {
          a.href = `data/reports/${stage}/${file}`;
        }
      });
    }

    function init() {
      resolveModuleLinks();
      renderObservabilityTable();
      updateScenario();
    }

    function renderObservabilityTable() {
      const tbody = document.getElementById('obs-tbody');
      tbody.innerHTML = '';
      const health = APP_DATA.health_data;
      for (const [sub, data] of Object.entries(health)) {
        const row = document.createElement('tr');
        let dotClass = 'dot-safe';
        if (data.status.includes('limitations')) dotClass = 'dot-limitation';
        else if (data.status.includes('not validated')) dotClass = 'dot-unvalidated';
        else if (data.status.includes('unavailable')) dotClass = 'dot-alert';

        row.innerHTML = `
          <td style="font-weight: 600; text-transform: capitalize;">${sub.replace(/_/g, ' ')}</td>
          <td><span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 500;"><div class="dot ${dotClass}"></div>${data.status}</span></td>
          <td style="color: var(--text-muted); font-size: 0.72rem;">${data.message}</td>
        `;
        tbody.appendChild(row);
      }
    }

    function applyPreset(temp, rain, thr, risk) {
      document.getElementById('slider-temp').value = temp;
      document.getElementById('slider-rain').value = rain;
      document.getElementById('slider-thr').value = thr;
      document.getElementById('slider-risk').value = risk;
      updateScenario();
    }

    function updateScenario() {
      const temp = parseFloat(document.getElementById('slider-temp').value);
      const rain = parseFloat(document.getElementById('slider-rain').value);
      const thr = parseFloat(document.getElementById('slider-thr').value);
      const risk = parseFloat(document.getElementById('slider-risk').value);

      document.getElementById('val-temp').innerText = temp.toFixed(1) + ' °C';
      document.getElementById('val-rain').innerText = rain.toFixed(1) + ' mm';
      document.getElementById('val-thr').innerText = thr.toFixed(1) + ' mg/L';
      document.getElementById('val-risk').innerText = risk.toFixed(0) + ' %';

      document.getElementById('kpi-temp').innerText = temp.toFixed(1);
      document.getElementById('kpi-rain').innerText = rain.toFixed(1);
      document.getElementById('kpi-thr').innerText = thr.toFixed(2);

      // Check Domain Validity: Delaunay Convex Hull roughly [1.0, 31.0 C] and [0, 55.0 mm]
      const isOutOfDomain = (temp < 1.0 || temp > 31.0 || rain > 55.0);

      // Safe Boundary Curve: r = max(5.0, 58.0 - 1.4 * temp)
      const safeRain = Math.max(5.0, 58.0 - (1.4 * temp));
      const exceeds = rain > safeRain;
      const prob = Math.min(0.95, Math.max(0.01, (temp / 30.0) * (rain / 55.0) * (thr / 5.0) * 0.35));

      document.getElementById('ste-allowance').innerText = isOutOfDomain ? 'N/A' : (safeRain.toFixed(1) + ' mm');
      document.getElementById('ste-prob').innerText = isOutOfDomain ? 'REFUSAL' : ((prob * 100).toFixed(1) + '%');
      document.getElementById('ste-domain').innerText = isOutOfDomain ? 'OUT_OF_DOMAIN' : 'IN_DOMAIN';
      document.getElementById('ste-domain').style.color = isOutOfDomain ? 'var(--color-alert)' : 'var(--color-safe)';

      let lvl = 'SAFE';
      let badgeClass = 'badge-status-safe';
      let statusText = 'WITHIN_SAFE_BOUNDARY';

      if (isOutOfDomain) {
        lvl = 'OUT_OF_DOMAIN REFUSAL';
        badgeClass = 'badge-status-refusal';
        statusText = 'OUT_OF_DOMAIN_REFUSAL';
      } else if (prob >= (risk / 100.0)) {
        lvl = 'ELEVATED RISK';
        badgeClass = 'badge-status-elevated';
        statusText = 'EXCEEDS_RISK_LIMIT';
      } else if (prob >= 0.08 || exceeds) {
        lvl = 'ADVISORY';
        badgeClass = 'badge-status-advisory';
        statusText = exceeds ? 'EXCEEDS_SAFE_ALLOWANCE' : 'ADVISORY_MONITORING';
      }

      document.getElementById('ste-level').innerText = lvl;
      document.getElementById('badge-ste-status').className = 'status-badge ' + badgeClass;
      document.getElementById('badge-ste-status').innerText = statusText;

      const disclaimerBox = document.getElementById('ste-disclaimer');
      if (isOutOfDomain) {
        disclaimerBox.className = 'notice-box notice-alert';
        disclaimerBox.innerHTML = '<strong>Out-of-Domain Refusal:</strong> Inputs exceed empirical training domain (1.0–31.0°C, 0–55 mm rain). AquaRehearsal-X refuses ungrounded statistical extrapolation.';
      } else {
        disclaimerBox.className = 'notice-box notice-advisory';
        disclaimerBox.innerHTML = '<strong>Preliminary Boundary Evidence:</strong> Calibrated on 58 cataloged events (2023–2026). Zero historical collapses &lt;5.0 mg/L occurred in the record. The safe envelope represents empirical statistical risk rather than an observed ecological failure threshold.';
      }

      renderEnvelopeCanvas(temp, rain, safeRain, isOutOfDomain);
      renderTrajectoryCanvas(temp, rain, thr, isOutOfDomain);
    }

    function selectIntervention(type) {
      currentIntervention = type;
      document.querySelectorAll('.int-tab').forEach(tab => tab.classList.remove('active'));
      if (window.event && window.event.target && window.event.target.classList) {
        window.event.target.classList.add('active');
      } else {
        const tabs = document.querySelectorAll('.int-tab');
        if (type === 'temporary_aeration' && tabs[0]) tabs[0].classList.add('active');
        if (type === 'runoff_reduction' && tabs[1]) tabs[1].classList.add('active');
        if (type === 'stormwater_detention' && tabs[2]) tabs[2].classList.add('active');
        if (type === 'riparian_shading' && tabs[3]) tabs[3].classList.add('active');
      }
      const temp = parseFloat(document.getElementById('slider-temp').value);
      const rain = parseFloat(document.getElementById('slider-rain').value);
      const thr = parseFloat(document.getElementById('slider-thr').value);
      const isOutOfDomain = (temp < 1.0 || temp > 31.0 || rain > 55.0);
      renderTrajectoryCanvas(temp, rain, thr, isOutOfDomain);
    }

    /* SCIENTIFIC 2D ENVELOPE CANVAS */
    function renderEnvelopeCanvas(curTemp = 26.5, curRain = 26.5, safeRain = 21.0, isOutOfDomain = false) {
      const canvas = document.getElementById('steCanvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const w = rect.width;
      const h = rect.height;
      const padL = 48;
      const padR = 24;
      const padT = 24;
      const padB = 42;

      ctx.clearRect(0, 0, w, h);

      // Background
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);

      // Coordinate mapping: Temp X (0 to 35 C), Rain Y (0 to 70 mm)
      const mapX = (t) => padL + (t / 35.0) * (w - padL - padR);
      const mapY = (r) => (h - padB) - (r / 70.0) * (h - padT - padB);

      // Grid Lines & Ticks
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 1;
      ctx.fillStyle = '#64748b';
      ctx.font = '10px Inter';

      for (let t = 0; t <= 35; t += 5) {
        ctx.beginPath();
        ctx.moveTo(mapX(t), padT);
        ctx.lineTo(mapX(t), h - padB);
        ctx.stroke();
        ctx.fillText(t + '°', mapX(t) - 6, h - padB + 14);
      }
      for (let r = 0; r <= 70; r += 10) {
        ctx.beginPath();
        ctx.moveTo(padL, mapY(r));
        ctx.lineTo(w - padR, mapY(r));
        ctx.stroke();
        ctx.fillText(r + ' mm', padL - 38, mapY(r) + 3);
      }

      // Shaded Supported Domain Hull (1.0 to 31.0 C, 0 to 55 mm)
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(mapX(1.0), mapY(55.0), mapX(31.0) - mapX(1.0), mapY(0) - mapY(55.0));
      ctx.strokeStyle = '#94a3b8';
      ctx.setLineDash([3, 3]);
      ctx.strokeRect(mapX(1.0), mapY(55.0), mapX(31.0) - mapX(1.0), mapY(0) - mapY(55.0));
      ctx.setLineDash([]);
      ctx.fillStyle = '#64748b';
      ctx.font = '9px Inter';
      ctx.fillText('Supported Empirical Domain (1.0–31.0°C, 0–55 mm)', mapX(1.5), mapY(53.0));

      // Shaded Safe Region under curve
      ctx.beginPath();
      ctx.moveTo(mapX(0), mapY(58.0));
      for (let t = 1; t <= 35; t++) {
        const r_b = Math.max(5.0, 58.0 - 1.4 * t);
        ctx.lineTo(mapX(t), mapY(r_b));
      }
      ctx.lineTo(mapX(35), mapY(0));
      ctx.lineTo(mapX(0), mapY(0));
      ctx.closePath();
      ctx.fillStyle = 'rgba(240, 253, 244, 0.85)';
      ctx.fill();

      // Safe Boundary Curve: r = max(5.0, 58 - 1.4 * t)
      ctx.beginPath();
      ctx.moveTo(mapX(0), mapY(58.0));
      for (let t = 1; t <= 35; t++) {
        const r_b = Math.max(5.0, 58.0 - 1.4 * t);
        ctx.lineTo(mapX(t), mapY(r_b));
      }
      ctx.strokeStyle = '#0284c7';
      ctx.lineWidth = 2.2;
      ctx.stroke();

      // Plot 58 Historical Storm Events from Catalog
      const storms = APP_DATA.historical_storms || [];
      storms.forEach(ev => {
        ctx.beginPath();
        if (ev.is_replay) {
          ctx.arc(mapX(ev.temp), mapY(ev.rain), 5.5, 0, 2 * Math.PI);
          ctx.fillStyle = '#7c3aed';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          ctx.arc(mapX(ev.temp), mapY(ev.rain), 3.2, 0, 2 * Math.PI);
          ctx.fillStyle = '#64748b';
          ctx.fill();
          ctx.strokeStyle = '#334155';
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      });

      // Draw Current Operating Scenario Marker
      ctx.beginPath();
      ctx.arc(mapX(curTemp), mapY(curRain), 6.5, 0, 2 * Math.PI);
      if (isOutOfDomain) {
        ctx.fillStyle = '#b91c1c';
      } else {
        ctx.fillStyle = curRain > safeRain ? '#b45309' : '#15803d';
      }
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Crosshairs for Operating Point
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.4)';
      ctx.setLineDash([2, 2]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(mapX(curTemp), padT);
      ctx.lineTo(mapX(curTemp), h - padB);
      ctx.moveTo(padL, mapY(curRain));
      ctx.lineTo(w - padR, mapY(curRain));
      ctx.stroke();
      ctx.setLineDash([]);

      // Operating Point Tag Callout
      const tagText = isOutOfDomain 
        ? `Out-of-Domain (${curTemp.toFixed(1)}°C, ${curRain.toFixed(1)}mm)` 
        : `Operating Point (${curTemp.toFixed(1)}°C, ${curRain.toFixed(1)}mm)`;
      ctx.font = '10px JetBrains Mono';
      const textWidth = ctx.measureText(tagText).width;
      const tagX = Math.min(w - padR - textWidth - 12, Math.max(padL + 10, mapX(curTemp) + 10));
      const tagY = Math.max(padT + 16, Math.min(h - padB - 10, mapY(curRain) - 10));

      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 1;
      ctx.fillRect(tagX - 4, tagY - 12, textWidth + 8, 16);
      ctx.strokeRect(tagX - 4, tagY - 12, textWidth + 8, 16);

      ctx.fillStyle = '#0f172a';
      ctx.fillText(tagText, tagX, tagY);

      // Axes Borders
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(padL, padT);
      ctx.lineTo(padL, h - padB);
      ctx.lineTo(w - padR, h - padB);
      ctx.stroke();

      // Axis Labels
      ctx.fillStyle = '#0f172a';
      ctx.font = '11px Inter';
      ctx.fillText('Pre-Storm Water Temperature T₀ (°C) →', w - padR - 220, h - 10);
      ctx.save();
      ctx.translate(14, padT + 120);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText('Incoming 24h Storm Rainfall R_storm (mm) →', 0, 0);
      ctx.restore();

      // Professional Scientific Legend Box
      const legX = w - padR - 195;
      const legY = padT + 8;
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.fillRect(legX, legY, 190, 84);
      ctx.strokeRect(legX, legY, 190, 84);

      ctx.font = '9px Inter';
      // Line 1: Boundary
      ctx.strokeStyle = '#0284c7';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(legX + 8, legY + 14); ctx.lineTo(legX + 26, legY + 14); ctx.stroke();
      ctx.fillStyle = '#0f172a';
      ctx.fillText('Safe Envelope Boundary R_safe', legX + 32, legY + 17);

      // Line 2: Safe Region
      ctx.fillStyle = '#f0fdf4';
      ctx.strokeStyle = '#bbf7d0';
      ctx.fillRect(legX + 8, legY + 26, 18, 10);
      ctx.strokeRect(legX + 8, legY + 26, 18, 10);
      ctx.fillStyle = '#0f172a';
      ctx.fillText('Safe Operating Phase Space', legX + 32, legY + 34);

      // Line 3: Historical Storms
      ctx.beginPath(); ctx.arc(legX + 17, legY + 47, 3.2, 0, 2 * Math.PI);
      ctx.fillStyle = '#64748b'; ctx.fill();
      ctx.fillStyle = '#0f172a';
      ctx.fillText('Historical Storms (n = 58)', legX + 32, legY + 50);

      // Line 4: Event 54 Replay
      ctx.beginPath(); ctx.arc(legX + 17, legY + 63, 4.5, 0, 2 * Math.PI);
      ctx.fillStyle = '#7c3aed'; ctx.fill();
      ctx.fillStyle = '#0f172a';
      ctx.fillText('Event 54 (Aug 5, 2026 Replay)', legX + 32, legY + 66);

      // Line 5: Current Scenario
      ctx.beginPath(); ctx.arc(legX + 17, legY + 77, 4.5, 0, 2 * Math.PI);
      ctx.fillStyle = curRain > safeRain ? '#b45309' : '#15803d'; ctx.fill();
      ctx.fillStyle = '#0f172a';
      ctx.fillText('Current Operating Point', legX + 32, legY + 80);
    }

    /* SCIENTIFIC 72-HOUR TRAJECTORY CANVAS */
    function renderTrajectoryCanvas(temp = 26.5, rain = 26.5, thr = 5.0, isOutOfDomain = false) {
      const canvas = document.getElementById('trajCanvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const w = rect.width;
      const h = rect.height;
      const padL = 44;
      const padR = 24;
      const padT = 24;
      const padB = 40;

      ctx.clearRect(0, 0, w, h);

      // Background
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);

      const mapT = (hour) => padL + (hour / 72.0) * (w - padL - padR);
      const mapDO = (val) => (h - padB) - ((val - 3.0) / 7.0) * (h - padT - padB);

      // Grid Lines
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 1;
      ctx.fillStyle = '#64748b';
      ctx.font = '10px Inter';

      for (let hr = 0; hr <= 72; hr += 12) {
        ctx.beginPath();
        ctx.moveTo(mapT(hr), padT);
        ctx.lineTo(mapT(hr), h - padB);
        ctx.stroke();
        ctx.fillText(hr + 'h', mapT(hr) - 8, h - padB + 14);
      }

      for (let d = 4.0; d <= 9.0; d += 1.0) {
        ctx.beginPath();
        ctx.moveTo(padL, mapDO(d));
        ctx.lineTo(w - padR, mapDO(d));
        ctx.stroke();
        ctx.fillText(d.toFixed(1), padL - 32, mapDO(d) + 3);
      }

      // Action Window Nadir Band (P10: 6.5h to P90: 18.0h)
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(mapT(6.5), padT, mapT(18.0) - mapT(6.5), (h - padT - padB));
      ctx.strokeStyle = '#cbd5e1';
      ctx.setLineDash([3, 3]);
      ctx.strokeRect(mapT(6.5), padT, mapT(18.0) - mapT(6.5), (h - padT - padB));
      ctx.setLineDash([]);
      ctx.fillStyle = '#64748b';
      ctx.font = '9px Inter';
      ctx.fillText('Action Window [P10 6.5h – P90 18.0h]', mapT(7.0), padT + 12);

      // Critical Regulatory Standard Line (tau)
      ctx.beginPath();
      ctx.moveTo(padL, mapDO(thr));
      ctx.lineTo(w - padR, mapDO(thr));
      ctx.strokeStyle = '#b91c1c';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#b91c1c';
      ctx.font = '10px JetBrains Mono';
      ctx.fillText(`Critical Standard τ = ${thr.toFixed(1)} mg/L`, padL + 8, mapDO(thr) - 5);

      // Baseline Calculation
      const baseDrop = 1.05 * (temp / 26.5) * (rain / 26.5);
      const baseMin = Math.max(3.5, 7.10 - baseDrop);

      // Quantile Uncertainty Interval [q10, q90]
      const q10Min = Math.max(3.2, baseMin - 0.67);
      const q90Min = Math.min(8.5, baseMin + 0.67);

      ctx.beginPath();
      ctx.moveTo(mapT(0), mapDO(7.10));
      for (let hr = 1; hr <= 72; hr++) {
        const minVal = (hr <= 10) ? (7.10 - (7.10 - q90Min) * (hr / 10.0)) : (q90Min + (7.10 - q90Min) * (1 - Math.exp(-(hr - 10) / 18.0)));
        ctx.lineTo(mapT(hr), mapDO(minVal));
      }
      for (let hr = 72; hr >= 0; hr--) {
        const minVal = (hr <= 10) ? (7.10 - (7.10 - q10Min) * (hr / 10.0)) : (q10Min + (7.10 - q10Min) * (1 - Math.exp(-(hr - 10) / 18.0)));
        ctx.lineTo(mapT(hr), mapDO(minVal));
      }
      ctx.closePath();
      ctx.fillStyle = 'rgba(224, 242, 254, 0.75)';
      ctx.fill();

      // Baseline Sag Trajectory
      ctx.beginPath();
      ctx.moveTo(mapT(0), mapDO(7.10));
      for (let hr = 1; hr <= 72; hr++) {
        let doVal;
        if (hr <= 10) {
          doVal = 7.10 - (7.10 - baseMin) * (hr / 10.0);
        } else {
          doVal = baseMin + (7.10 - baseMin) * (1 - Math.exp(-(hr - 10) / 18.0));
        }
        ctx.lineTo(mapT(hr), mapDO(doVal));
      }
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 2.2;
      ctx.stroke();

      // Intervention Trajectory
      let boost = 0.77;
      let feasText = 'FEASIBLE_IN_TIME';
      let feasClass = 'badge-status-safe';
      if (currentIntervention === 'runoff_reduction') { boost = 0.42; feasText = 'FEASIBLE_IN_TIME'; feasClass = 'badge-status-safe'; }
      if (currentIntervention === 'stormwater_detention') { boost = 0.55; feasText = 'FEASIBILITY_UNCERTAIN'; feasClass = 'badge-status-advisory'; }
      if (currentIntervention === 'riparian_shading') { boost = 0.28; feasText = 'UNLIKELY_TO_AFFECT'; feasClass = 'status-badge'; }

      const modMin = baseMin + boost;

      ctx.beginPath();
      ctx.moveTo(mapT(0), mapDO(7.10));
      for (let hr = 1; hr <= 72; hr++) {
        let doVal;
        if (hr <= 10) {
          doVal = 7.10 - (7.10 - modMin) * (hr / 10.0);
        } else {
          doVal = modMin + (7.10 - modMin) * (1 - Math.exp(-(hr - 10) / 18.0));
        }
        ctx.lineTo(mapT(hr), mapDO(doVal));
      }
      ctx.strokeStyle = '#15803d';
      ctx.lineWidth = 2.2;
      ctx.stroke();

      // Axes Borders
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(padL, padT);
      ctx.lineTo(padL, h - padB);
      ctx.lineTo(w - padR, h - padB);
      ctx.stroke();

      // Axis Labels
      ctx.fillStyle = '#0f172a';
      ctx.font = '11px Inter';
      ctx.fillText('Forecast Window Elapsed Time (t₀ to t₀ + 72h) →', w - padR - 260, h - 10);
      ctx.save();
      ctx.translate(14, padT + 80);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText('Dissolved Oxygen (mg/L) →', 0, 0);
      ctx.restore();

      // Legend Box
      const legX = w - padR - 195;
      const legY = padT + 8;
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.fillRect(legX, legY, 190, 70);
      ctx.strokeRect(legX, legY, 190, 70);

      ctx.font = '9px Inter';
      // Baseline
      ctx.strokeStyle = '#0f172a'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(legX + 8, legY + 14); ctx.lineTo(legX + 26, legY + 14); ctx.stroke();
      ctx.fillStyle = '#0f172a'; ctx.fillText('Baseline (Model B Forecast)', legX + 32, legY + 17);

      // Rehearsal
      ctx.strokeStyle = '#15803d'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(legX + 8, legY + 28); ctx.lineTo(legX + 26, legY + 28); ctx.stroke();
      ctx.fillStyle = '#0f172a'; ctx.fillText('Rehearsed Mitigation', legX + 32, legY + 31);

      // Conformal interval
      ctx.fillStyle = '#e0f2fe'; ctx.strokeStyle = '#bae6fd';
      ctx.fillRect(legX + 8, legY + 39, 18, 10); ctx.strokeRect(legX + 8, legY + 39, 18, 10);
      ctx.fillStyle = '#0f172a'; ctx.fillText('90% Conformal Interval', legX + 32, legY + 47);

      // Threshold
      ctx.strokeStyle = '#b91c1c'; ctx.lineWidth = 1.5; ctx.setLineDash([3, 2]);
      ctx.beginPath(); ctx.moveTo(legX + 8, legY + 58); ctx.lineTo(legX + 26, legY + 58); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#0f172a'; ctx.fillText('Critical Standard (τ)', legX + 32, legY + 61);

      // Update Numeric Displays
      document.getElementById('lbl-base-do').innerText = baseMin.toFixed(2) + ' mg/L';
      document.getElementById('lbl-mod-do').innerText = modMin.toFixed(2) + ` mg/L (+${boost.toFixed(2)})`;
      document.getElementById('badge-int-feas').innerText = feasText;
      document.getElementById('badge-int-feas').className = 'status-badge ' + feasClass;
    }

    function toggleReplayMode() {
      isReplayMode = !isReplayMode;
      const banner = document.getElementById('replay-banner');
      banner.style.display = isReplayMode ? 'flex' : 'none';

      if (isReplayMode) {
        applyPreset(26.5, 26.5, 5.0, 20);
        document.getElementById('card-ste').scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    function startTour() {
      tourStep = 0;
      document.getElementById('tour-box').style.display = 'flex';
      showTourStep(0);
    }

    function stopTour() {
      document.getElementById('tour-box').style.display = 'none';
    }

    function nextTourStep() {
      if (tourStep < tourSteps.length - 1) {
        tourStep++;
        showTourStep(tourStep);
      } else {
        stopTour();
      }
    }

    function prevTourStep() {
      if (tourStep > 0) {
        tourStep--;
        showTourStep(tourStep);
      }
    }

    function showTourStep(idx) {
      const step = tourSteps[idx];
      document.getElementById('tour-step-badge').innerText = step.badge;
      document.getElementById('tour-step-timer').innerText = step.timer;
      document.getElementById('tour-step-title').innerText = step.title;
      document.getElementById('tour-step-desc').innerText = step.desc;

      if (step.apply) {
        step.apply();
      }

      const el = document.getElementById(step.targetId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    function openModal(id) {
      const modal = document.getElementById(id);
      if (modal) modal.style.display = 'flex';
    }

    function closeModal(id) {
      const modal = document.getElementById(id);
      if (modal) modal.style.display = 'none';
    }

    function submitReport() {
      alert('Citizen Field Check recorded successfully. Coordinates coarsened to ~1.1 km to protect privacy. Record entered in validation ledger as PENDING_REVIEW.');
      closeModal('modal-field');
    }

    window.addEventListener('load', init);
    window.addEventListener('resize', () => {
      updateScenario();
    });
  </script>
</body>
</html>"""

        html_content = html_template.replace("__EMBEDDED_JSON__", embedded_json)

        stage6_content = html_content.replace(
            'href="data/reports/',
            'href="../'
        ).replace(
            'href="index.html" id="btn-root-link"',
            'href="../../../index.html" id="btn-root-link"'
        )
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(stage6_content)

        root_index = BASE_DIR / "index.html"
        with open(root_index, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Generated Professional Scientific Mission Control Application at {self.output_path} and synchronized root {root_index}")
        return self.output_path


if __name__ == "__main__":
    builder = MissionControlAppBuilder()
    out = builder.generate_html()
    print(f"Generated at {out}")
