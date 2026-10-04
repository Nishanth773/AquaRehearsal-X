"""
AquaRehearsal-X - Stage 2.5 Data Coverage Audit
Historical Depth + Real Precipitation Upgrade

Compares Stage 2 (Current 6-Month Dataset) against Stage 2.5 (Extended 3.75-Year Dataset).
Audits:
- Total span in years and days
- Total observation counts
- Per-parameter completeness and missingness
- Precipitation statistics: measured 0.0 mm (dry) vs measured wet vs missing NaN
- Candidate disturbance events and valid 72h future target counts

Produces:
    data/reports/stage2_5/stage2_5_data_coverage.csv
"""

from pathlib import Path
from typing import Dict, Any
import numpy as np
import pandas as pd

from src.config.stage2_5_settings import (
    STAGE2_5_DATA_CONFIG,
    STAGE2_5_REPORTS_DIR,
    PROCESSED_DATA_DIR,
)
from src.features.target_builder import TargetBuilder
from src.utils.logger import logger


class DataCoverageAuditor:
    """Computes comprehensive audit comparing current vs extended datasets."""

    def __init__(self):
        self.stage2_csv = PROCESSED_DATA_DIR / STAGE2_5_DATA_CONFIG["stage2_baseline_data_file"]
        self.extended_csv = PROCESSED_DATA_DIR / STAGE2_5_DATA_CONFIG["extended_data_file"]
        self.reports_dir = STAGE2_5_REPORTS_DIR

    def generate_audit_report(self) -> pd.DataFrame:
        """Audits both datasets and saves comparison CSV."""
        logger.info("Auditing Stage 2 baseline vs Stage 2.5 extended dataset...")

        df_curr = pd.read_csv(self.stage2_csv)
        df_ext = pd.read_csv(self.extended_csv)

        # Convert timestamps
        df_curr["timestamp"] = pd.to_datetime(df_curr["timestamp"], utc=True)
        df_ext["timestamp"] = pd.to_datetime(df_ext["timestamp"], utc=True)

        # Compute targets to check valid 72h windows
        tgt_builder = TargetBuilder(horizon_hours=72, min_valid_hours=58)
        df_curr_tgt = tgt_builder.compute_72h_minimum_target(df_curr, output_col="target")
        df_ext_tgt = tgt_builder.compute_72h_minimum_target(df_ext, output_col="target")

        curr_valid_targets = int(df_curr_tgt["target"].notna().sum())
        ext_valid_targets = int(df_ext_tgt["target"].notna().sum())

        # Dates & Span
        curr_start = df_curr["timestamp"].min()
        curr_end = df_curr["timestamp"].max()
        curr_span_days = (curr_end - curr_start).total_seconds() / 86400.0

        ext_start = df_ext["timestamp"].min()
        ext_end = df_ext["timestamp"].max()
        ext_span_days = (ext_end - ext_start).total_seconds() / 86400.0

        # Precipitation & Liquid Rain statistics for extended dataset
        rain_col = "rain_mm"
        if rain_col in df_ext.columns:
            r = df_ext[rain_col]
            ext_r_valid = int(r.notna().sum())
            ext_r_missing = int(r.isna().sum())
            ext_r_missing_pct = round((ext_r_missing / len(df_ext)) * 100.0, 2)
            ext_r_zero = int((r == 0.0).sum())
            ext_r_zero_pct = round((ext_r_zero / len(df_ext)) * 100.0, 2)
            ext_r_wet = int((r > 0.0).sum())
            ext_r_wet_pct = round((ext_r_wet / len(df_ext)) * 100.0, 2)
            ext_r_max = float(r.max())
            ext_r_sum = float(r.sum())
        else:
            ext_r_valid = 0
            ext_r_missing = len(df_ext)
            ext_r_missing_pct = 100.0
            ext_r_zero = 0
            ext_r_zero_pct = 0.0
            ext_r_wet = 0
            ext_r_wet_pct = 0.0
            ext_r_max = 0.0
            ext_r_sum = 0.0

        precip_col = "precipitation_mm"
        if precip_col in df_ext.columns:
            p = df_ext[precip_col]
            ext_p_valid = int(p.notna().sum())
            ext_p_missing = int(p.isna().sum())
            ext_p_missing_pct = round((ext_p_missing / len(df_ext)) * 100.0, 2)
            ext_p_max = float(p.max())
            ext_p_sum = float(p.sum())
        else:
            ext_p_valid = 0
            ext_p_missing = len(df_ext)
            ext_p_missing_pct = 100.0
            ext_p_max = 0.0
            ext_p_sum = 0.0

        # Parameter Completeness
        curr_do_pct = round((df_curr["dissolved_oxygen"].notna().sum() / len(df_curr)) * 100.0, 2)
        ext_do_pct = round((df_ext["dissolved_oxygen"].notna().sum() / len(df_ext)) * 100.0, 2)

        curr_temp_pct = round((df_curr["water_temperature"].notna().sum() / len(df_curr)) * 100.0, 2)
        ext_temp_pct = round((df_ext["water_temperature"].notna().sum() / len(df_ext)) * 100.0, 2)

        curr_q_pct = round((df_curr["discharge"].notna().sum() / len(df_curr)) * 100.0, 2)
        ext_q_pct = round((df_ext["discharge"].notna().sum() / len(df_ext)) * 100.0, 2)

        curr_turb_pct = round((df_curr["turbidity"].notna().sum() / len(df_curr)) * 100.0, 2)
        ext_turb_pct = round((df_ext["turbidity"].notna().sum() / len(df_ext)) * 100.0, 2)

        audit_data = [
            {"METRIC": "Station Identifier", "STAGE_2_CURRENT": "USGS 01474500", "STAGE_2_5_EXTENDED": "USGS 01474500"},
            {"METRIC": "Start Timestamp (UTC)", "STAGE_2_CURRENT": str(curr_start), "STAGE_2_5_EXTENDED": str(ext_start)},
            {"METRIC": "End Timestamp (UTC)", "STAGE_2_CURRENT": str(curr_end), "STAGE_2_5_EXTENDED": str(ext_end)},
            {"METRIC": "Temporal Span (Calendar Days)", "STAGE_2_CURRENT": f"{curr_span_days:.1f} days", "STAGE_2_5_EXTENDED": f"{ext_span_days:.1f} days"},
            {"METRIC": "Temporal Span (Years)", "STAGE_2_CURRENT": f"{curr_span_days / 365.25:.2f} years", "STAGE_2_5_EXTENDED": f"{ext_span_days / 365.25:.2f} years"},
            {"METRIC": "Total Hourly Observations", "STAGE_2_CURRENT": str(len(df_curr)), "STAGE_2_5_EXTENDED": str(len(df_ext))},
            {"METRIC": "Dissolved Oxygen Availability (%)", "STAGE_2_CURRENT": f"{curr_do_pct}%", "STAGE_2_5_EXTENDED": f"{ext_do_pct}%"},
            {"METRIC": "Water Temperature Availability (%)", "STAGE_2_CURRENT": f"{curr_temp_pct}%", "STAGE_2_5_EXTENDED": f"{ext_temp_pct}%"},
            {"METRIC": "Discharge Availability (%)", "STAGE_2_CURRENT": f"{curr_q_pct}%", "STAGE_2_5_EXTENDED": f"{ext_q_pct}%"},
            {"METRIC": "Turbidity Availability (%)", "STAGE_2_CURRENT": f"{curr_turb_pct}%", "STAGE_2_5_EXTENDED": f"{ext_turb_pct}% (deployed 2026-05)"},
            {"METRIC": "Meteorological API Source", "STAGE_2_CURRENT": "None (Decoupled)", "STAGE_2_5_EXTENDED": "Open-Meteo Historical Weather API"},
            {"METRIC": "Meteorological Exact Model", "STAGE_2_CURRENT": "None", "STAGE_2_5_EXTENDED": "ECMWF ERA5 Reanalysis (era5, 0.25 deg)"},
            {"METRIC": "Primary Storm Variable", "STAGE_2_CURRENT": "None", "STAGE_2_5_EXTENDED": "rain_mm (liquid precipitation)"},
            {"METRIC": "Liquid Rain Valid Observations", "STAGE_2_CURRENT": "0 (0.0%)", "STAGE_2_5_EXTENDED": f"{ext_r_valid} ({100.0 - ext_r_missing_pct}%)"},
            {"METRIC": "Liquid Rain Missingness (NaN)", "STAGE_2_CURRENT": "100.0%", "STAGE_2_5_EXTENDED": f"{ext_r_missing} ({ext_r_missing_pct}%)"},
            {"METRIC": "Liquid Rain Measured Dry Hours (0.0 mm)", "STAGE_2_CURRENT": "N/A", "STAGE_2_5_EXTENDED": f"{ext_r_zero} ({ext_r_zero_pct}%)"},
            {"METRIC": "Liquid Rain Measured Wet Hours (>0.0 mm)", "STAGE_2_CURRENT": "N/A", "STAGE_2_5_EXTENDED": f"{ext_r_wet} ({ext_r_wet_pct}%)"},
            {"METRIC": "Liquid Rain Peak Hourly Rate", "STAGE_2_CURRENT": "N/A", "STAGE_2_5_EXTENDED": f"{ext_r_max:.1f} mm/hr"},
            {"METRIC": "Liquid Rain Cumulative Sum", "STAGE_2_CURRENT": "N/A", "STAGE_2_5_EXTENDED": f"{ext_r_sum:.1f} mm"},
            {"METRIC": "Total Precipitation Cumulative Sum", "STAGE_2_CURRENT": "N/A", "STAGE_2_5_EXTENDED": f"{ext_p_sum:.1f} mm"},
            {"METRIC": "Valid 72h Future Target Windows", "STAGE_2_CURRENT": f"{curr_valid_targets} ({curr_valid_targets / len(df_curr) * 100:.1f}%)", "STAGE_2_5_EXTENDED": f"{ext_valid_targets} ({ext_valid_targets / len(df_ext) * 100:.1f}%)"},
            {"METRIC": "Seasonal Coverage", "STAGE_2_CURRENT": "Spring-Summer (Single Warm Season)", "STAGE_2_5_EXTENDED": "4 Springs, 4 Summers, 3 Falls, 3 Winters"},
        ]

        df_audit = pd.DataFrame(audit_data)
        out_csv = self.reports_dir / "stage2_5_data_coverage.csv"
        df_audit.to_csv(out_csv, index=False)
        logger.info("Saved data coverage comparison audit to %s", out_csv)
        return df_audit


if __name__ == "__main__":
    auditor = DataCoverageAuditor()
    df_rep = auditor.generate_audit_report()
    print(df_rep.to_string(index=False))
