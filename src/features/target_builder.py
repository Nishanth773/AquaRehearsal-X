"""
AquaRehearsal-X - Stage 2 Target Builder
72-Hour Dissolved Oxygen Forecasting Engine

Defines and computes the forecasting target:
    TARGET(t) = minimum observed dissolved oxygen during (t, t + 72 hours]

Strict Scientific Integrity Rules:
- Only future observations are used to construct the target.
- Future observations must NEVER appear in the input features.
- The observation at prediction time t is EXCLUDED from the target window.
- Incomplete windows or windows with insufficient future observations are set to NaN.
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

from src.config.stage2_settings import STAGE2_TARGET_CONFIG
from src.utils.logger import logger


class TargetBuilder:
    """Computes the future 72-hour minimum dissolved oxygen target."""

    def __init__(
        self,
        target_col: str = "dissolved_oxygen",
        horizon_hours: int = 72,
        min_valid_hours: int = 58,
    ):
        """
        Args:
            target_col: Column name of dissolved oxygen sensor series.
            horizon_hours: Future forecasting horizon in hours (default: 72).
            min_valid_hours: Minimum non-null observations required in (t, t+72h] (default: 58, ~80%).
        """
        self.target_col = target_col
        self.horizon_hours = horizon_hours
        self.min_valid_hours = min_valid_hours

    def compute_72h_minimum_target(
        self,
        df: pd.DataFrame,
        output_col: str = "target_min_do_72h",
    ) -> pd.DataFrame:
        """
        Computes the future minimum dissolved oxygen for each timestamp t over (t, t + 72h].

        Implementation:
        For regular 1-hour time series, the future window for row i spans rows [i+1, i+72].
        We compute the backward rolling minimum and count on the reversed series,
        then shift by -1. This ensures observation at timestamp t is strictly excluded.

        Args:
            df: DataFrame indexed by or containing 'timestamp', sorted chronologically.
            output_col: Name of target column to produce.

        Returns:
            DataFrame with new target column.
        """
        if df.empty:
            df_out = df.copy()
            df_out[output_col] = pd.Series(dtype=float)
            return df_out

        df_out = df.copy()
        if self.target_col not in df_out.columns:
            raise KeyError(f"Target column '{self.target_col}' not found in DataFrame.")

        series = df_out[self.target_col].copy()

        # Reverse the series to apply backward rolling over future observations
        reversed_series = series.iloc[::-1]

        # Rolling minimum on reversed series over horizon_hours
        rolled_min_rev = reversed_series.rolling(
            window=self.horizon_hours,
            min_periods=self.min_valid_hours,
        ).min()

        # Rolling valid count to verify sufficiency
        rolled_count_rev = reversed_series.rolling(
            window=self.horizon_hours,
            min_periods=1,
        ).count()

        # Reverse back to chronological order and shift by -1 so row t looks at (t, t + horizon_hours]
        rolled_min = rolled_min_rev.iloc[::-1].shift(-1)
        rolled_count = rolled_count_rev.iloc[::-1].shift(-1)

        # Invalidate rows where valid future observations < min_valid_hours
        rolled_min[rolled_count < self.min_valid_hours] = np.nan

        df_out[output_col] = rolled_min

        total_rows = len(df_out)
        valid_targets = int(df_out[output_col].notna().sum())
        logger.info(
            "Computed 72h minimum target '%s': %d/%d valid rows (%.2f%%).",
            output_col,
            valid_targets,
            total_rows,
            (valid_targets / total_rows * 100.0) if total_rows > 0 else 0.0,
        )
        return df_out

    @staticmethod
    def filter_valid_targets(
        df: pd.DataFrame,
        target_col: str = "target_min_do_72h",
    ) -> pd.DataFrame:
        """
        Filters out rows where target is NaN (e.g. at the end of the series or large gaps).
        """
        valid_mask = df[target_col].notna()
        filtered = df[valid_mask].copy()
        logger.info("Filtered valid target rows: %d -> %d (dropped %d rows).", len(df), len(filtered), len(df) - len(filtered))
        return filtered
