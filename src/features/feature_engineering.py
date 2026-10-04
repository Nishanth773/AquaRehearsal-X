"""
AquaRehearsal-X - Future ML Feature Generation Architecture
Stage 1: Real Data Foundation

Defines modular feature engineering interfaces for future predictive modeling.
IMPORTANT:
- No ML models are trained in Stage 1.
- No predictive performance or feature superiority is claimed at this stage.
- Establishes reproducible transformations for lags, rolling statistics, and seasonal encodings.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.utils.logger import logger


class FeatureEngineer:
    """Architectural interface for feature extraction from clean sensor time series."""

    def __init__(self, default_lags: Optional[List[int]] = None):
        # Default lag steps (e.g. at 15-min intervals: 1=15m, 4=1h, 16=4h, 96=24h)
        self.default_lags = default_lags or [1, 2, 4, 8, 16, 24, 96]

    def add_lag_features(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        lags: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """Generates lagged observation columns for specified variables."""
        if df.empty:
            return df.copy()

        df_out = df.copy()
        target_cols = columns or [c for c in ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"] if c in df.columns]
        lag_steps = lags or self.default_lags

        for col in target_cols:
            for lag in lag_steps:
                df_out[f"{col}_lag_{lag}"] = df_out[col].shift(lag)

        logger.debug("Added %d lag features across %d columns.", len(lag_steps) * len(target_cols), len(target_cols))
        return df_out

    def add_rolling_features(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        windows: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Generates rolling window statistics (mean, max, std) for hydrologic dynamics."""
        if df.empty:
            return df.copy()

        df_out = df.copy()
        target_cols = columns or [c for c in ["discharge", "turbidity", "water_temperature"] if c in df.columns]
        roll_windows = windows or ["1h", "6h", "24h", "72h"]

        for col in target_cols:
            for win in roll_windows:
                rolled = df_out[col].rolling(win, min_periods=1)
                df_out[f"{col}_roll_{win}_mean"] = rolled.mean()
                df_out[f"{col}_roll_{win}_max"] = rolled.max()
                df_out[f"{col}_roll_{win}_std"] = rolled.std()

        logger.debug("Added rolling features for windows %s across columns %s.", roll_windows, target_cols)
        return df_out

    def add_cyclical_seasonal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates cyclical sine/cosine encodings for hour-of-day (diurnal cycle)
        and day-of-year (annual cycle).
        """
        if df.empty:
            return df.copy()

        df_out = df.copy()
        hour = df_out.index.hour + df_out.index.minute / 60.0
        doy = df_out.index.dayofyear

        # Diurnal (24-hour periodicity)
        df_out["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
        df_out["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)

        # Annual (365.25-day periodicity)
        df_out["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
        df_out["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

        return df_out

    def build_candidate_feature_matrix(
        self,
        df: pd.DataFrame,
        include_lags: bool = True,
        include_rolling: bool = True,
        include_seasonal: bool = True,
    ) -> pd.DataFrame:
        """
        Combines base variables with candidate engineered features.
        Prepares structure for future Stage 2 ML exploration.
        """
        result = df.copy()
        if include_seasonal:
            result = self.add_cyclical_seasonal_features(result)
        if include_rolling:
            result = self.add_rolling_features(result)
        if include_lags:
            result = self.add_lag_features(result)

        logger.info("Built candidate feature matrix with shape %s (features: %d)", result.shape, result.shape[1])
        return result
