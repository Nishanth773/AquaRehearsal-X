"""
AquaRehearsal-X - Descriptive and Seasonal Statistics Module
Stage 1: Real Data Foundation

Computes non-parametric and parametric statistics for DO, water temperature,
discharge, and turbidity, including monthly and seasonal stratifications.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.config.settings import REPORTS_DIR
from src.utils.logger import logger


class DescriptiveStatistics:
    """Computes comprehensive statistical summaries for environmental time series."""

    @staticmethod
    def calculate_overall_statistics(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates count, mean, std, min, 5%, 10%, 25%, median (50%),
        75%, 90%, 95%, max, and interquartile range (IQR).
        """
        numeric_cols = [c for c in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity", "gage_height"] if c in df.columns]
        if not numeric_cols or df.empty:
            return pd.DataFrame()

        records = []
        for col in numeric_cols:
            series = df[col].dropna()
            if series.empty:
                continue

            q25 = float(series.quantile(0.25))
            q75 = float(series.quantile(0.75))
            iqr = q75 - q25

            record = {
                "variable": col,
                "observation_count": int(series.count()),
                "mean": round(float(series.mean()), 3),
                "std": round(float(series.std()), 3),
                "min": round(float(series.min()), 3),
                "p05": round(float(series.quantile(0.05)), 3),
                "p10": round(float(series.quantile(0.10)), 3),
                "p25": round(q25, 3),
                "median_p50": round(float(series.median()), 3),
                "p75": round(q75, 3),
                "p90": round(float(series.quantile(0.90)), 3),
                "p95": round(float(series.quantile(0.95)), 3),
                "max": round(float(series.max()), 3),
                "iqr": round(iqr, 3),
            }
            records.append(record)

        stats_df = pd.DataFrame(records)
        return stats_df

    @staticmethod
    def calculate_monthly_statistics(df: pd.DataFrame) -> pd.DataFrame:
        """Calculates monthly summary statistics for seasonality assessment."""
        numeric_cols = [c for c in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"] if c in df.columns]
        if not numeric_cols or df.empty:
            return pd.DataFrame()

        df_month = df.copy()
        df_month["month"] = df_month.index.month
        month_names = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }
        df_month["month_name"] = df_month["month"].map(month_names)

        grouped = df_month.groupby(["month", "month_name"])
        results = []

        for (m_num, m_name), group in grouped:
            row = {"month": m_num, "month_name": m_name, "total_records": len(group)}
            for col in numeric_cols:
                series = group[col].dropna()
                if not series.empty:
                    row[f"{col}_mean"] = round(float(series.mean()), 2)
                    row[f"{col}_median"] = round(float(series.median()), 2)
                    row[f"{col}_min"] = round(float(series.min()), 2)
                    row[f"{col}_max"] = round(float(series.max()), 2)
                    row[f"{col}_std"] = round(float(series.std()), 2)
            results.append(row)

        monthly_df = pd.DataFrame(results).sort_values("month")
        return monthly_df

    @staticmethod
    def calculate_seasonal_statistics(df: pd.DataFrame) -> pd.DataFrame:
        """Calculates meteorological seasonal statistics (Winter, Spring, Summer, Fall)."""
        numeric_cols = [c for c in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"] if c in df.columns]
        if not numeric_cols or df.empty:
            return pd.DataFrame()

        def get_season(month: int) -> str:
            if month in (12, 1, 2):
                return "Winter"
            elif month in (3, 4, 5):
                return "Spring"
            elif month in (6, 7, 8):
                return "Summer"
            else:
                return "Fall"

        df_season = df.copy()
        df_season["season"] = df_season.index.month.map(get_season)

        results = []
        for season in ["Spring", "Summer", "Fall", "Winter"]:
            sub = df_season[df_season["season"] == season]
            if sub.empty:
                continue
            row = {"season": season, "record_count": len(sub)}
            for col in numeric_cols:
                series = sub[col].dropna()
                if not series.empty:
                    row[f"{col}_mean"] = round(float(series.mean()), 2)
                    row[f"{col}_median"] = round(float(series.median()), 2)
                    row[f"{col}_p10"] = round(float(series.quantile(0.10)), 2)
                    row[f"{col}_p90"] = round(float(series.quantile(0.90)), 2)
            results.append(row)

        return pd.DataFrame(results)

    def export_all_statistics(
        self,
        df: pd.DataFrame,
        station_id: str,
        output_dir: Path = REPORTS_DIR,
    ) -> Dict[str, pd.DataFrame]:
        """Calculates and exports descriptive, monthly, and seasonal statistics."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        overall = self.calculate_overall_statistics(df)
        monthly = self.calculate_monthly_statistics(df)
        seasonal = self.calculate_seasonal_statistics(df)

        if not overall.empty:
            overall.to_csv(out_dir / f"statistics_{station_id}_overall.csv", index=False)
        if not monthly.empty:
            monthly.to_csv(out_dir / f"statistics_{station_id}_monthly.csv", index=False)
        if not seasonal.empty:
            seasonal.to_csv(out_dir / f"statistics_{station_id}_seasonal.csv", index=False)

        logger.info("Saved statistical summaries for station %s", station_id)
        return {"overall": overall, "monthly": monthly, "seasonal": seasonal}
