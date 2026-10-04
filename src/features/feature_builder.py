"""
AquaRehearsal-X - Stage 2 Feature Engineering Engine
72-Hour Dissolved Oxygen Forecasting Engine

Defines strictly causal, leakage-free feature extraction for dissolved oxygen forecasting.
All features are computed exclusively using observations available at or before prediction time t.

Feature Categories:
1. Current State (DO, Temperature, Discharge, Turbidity)
2. Physical Biogeochemical Features (DO saturation, DO deficit, saturation ratio)
3. Lag Features (t-1h, t-2h, t-3h, t-6h, t-12h, t-24h, t-48h, t-72h)
4. Rolling Backward Statistics (mean, min, max, std over 6h, 12h, 24h, 48h, 72h)
5. Change Features (recent deltas and rate of change over 1h, 3h, 6h, 24h)
6. Seasonal / Diurnal Cyclical Encodings (sine/cosine of hour and day of year)
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config.stage2_settings import STAGE2_FEATURE_CONFIG
from src.utils.logger import logger


class FeatureBuilder:
    """Extracts leakage-free predictive features from sensor time series."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or STAGE2_FEATURE_CONFIG
        self.base_cols = self.config.get(
            "base_sensor_columns",
            ["dissolved_oxygen", "water_temperature", "discharge", "turbidity"],
        )
        self.lag_hours = self.config.get("lag_hours", [1, 2, 3, 6, 12, 24, 48, 72])
        self.rolling_windows = self.config.get("rolling_windows", ["6h", "12h", "24h", "48h", "72h"])
        self.change_hours = self.config.get("change_hours", [1, 3, 6, 24])

    @staticmethod
    def compute_theoretical_do_saturation(temp_celsius: pd.Series) -> pd.Series:
        """
        Computes theoretical dissolved oxygen saturation (mg/L) at standard 1 atm pressure
        using the standard Benson-Krause formulation (USGS standard).
        Formula:
            ln(DO_sat) = -139.34411 + (1.575701e5 / T_K) - (6.642308e7 / T_K^2)
                         + (1.243800e10 / T_K^3) - (8.621949e11 / T_K^4)
        """
        temp_k = temp_celsius + 273.15
        ln_do_sat = (
            -139.34411
            + (1.575701e5 / temp_k)
            - (6.642308e7 / (temp_k ** 2))
            + (1.243800e10 / (temp_k ** 3))
            - (8.621949e11 / (temp_k ** 4))
        )
        return np.exp(ln_do_sat)

    def add_physical_saturation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds physically grounded aquatic biogeochemical features:
        - Theoretical DO saturation (mg/L)
        - DO saturation deficit (DO_sat - DO_obs)
        - DO saturation ratio (DO_obs / DO_sat)
        """
        df_out = df.copy()
        if "water_temperature" in df_out.columns:
            do_sat = self.compute_theoretical_do_saturation(df_out["water_temperature"])
            df_out["theoretical_do_saturation"] = do_sat

            if "dissolved_oxygen" in df_out.columns:
                df_out["do_saturation_deficit"] = do_sat - df_out["dissolved_oxygen"]
                df_out["do_saturation_ratio"] = df_out["dissolved_oxygen"] / np.clip(do_sat, 1.0, 30.0)

        return df_out

    def add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds backward lag features X(t - k) for specified lag hours.
        Strictly looks into the past using positive shift values.
        """
        df_out = df.copy()
        available_cols = [c for c in self.base_cols if c in df_out.columns]

        for col in available_cols:
            for lag in self.lag_hours:
                # shift(lag) moves previous values forward to current index -> X(t - lag)
                df_out[f"{col}_lag_{lag}h"] = df_out[col].shift(lag)

        return df_out

    def add_rolling_backward_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds backward-looking rolling statistics (mean, min, max, std)
        over specified windows (e.g. 6h, 12h, 24h, 48h, 72h).
        Uses closed='right' so window strictly covers (t - window, t].
        """
        df_out = df.copy()
        available_cols = [c for c in self.base_cols if c in df_out.columns]

        # Ensure index is DatetimeIndex for time-based rolling
        is_dt_index = isinstance(df_out.index, pd.DatetimeIndex)

        for col in available_cols:
            for win in self.rolling_windows:
                # Parse window string (e.g. '6h' -> 6 hours)
                if is_dt_index:
                    rolled = df_out[col].rolling(win, min_periods=1, closed="right")
                else:
                    win_int = int(win.replace("h", "").replace("H", ""))
                    rolled = df_out[col].rolling(win_int, min_periods=1, closed="right")

                df_out[f"{col}_roll_{win}_mean"] = rolled.mean()
                df_out[f"{col}_roll_{win}_min"] = rolled.min()
                df_out[f"{col}_roll_{win}_max"] = rolled.max()
                df_out[f"{col}_roll_{win}_std"] = rolled.std()

        return df_out

    def add_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds backward change / rate of change features:
        - Absolute change: X(t) - X(t - k)
        - Discharge surge ratio: (Q(t) - Q(t - k)) / (Q(t - k) + 1.0)
        """
        df_out = df.copy()
        available_cols = [c for c in self.base_cols if c in df_out.columns]

        for col in available_cols:
            for chg in self.change_hours:
                lagged = df_out[col].shift(chg)
                df_out[f"{col}_change_{chg}h"] = df_out[col] - lagged
                if col == "discharge":
                    df_out[f"discharge_surge_ratio_{chg}h"] = (df_out[col] - lagged) / np.clip(lagged, 1.0, None)

        return df_out

    def add_cyclical_seasonal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds diurnal and annual cyclical encodings using sine and cosine transformations.
        Also adds month indicator.
        """
        df_out = df.copy()
        if isinstance(df_out.index, pd.DatetimeIndex):
            timestamps = df_out.index
        elif "timestamp" in df_out.columns:
            timestamps = pd.to_datetime(df_out["timestamp"])
        else:
            return df_out

        hour = timestamps.hour + timestamps.minute / 60.0
        doy = timestamps.dayofyear
        month = timestamps.month

        # Diurnal (24-hour cycle)
        df_out["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
        df_out["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)

        # Annual (365.25-day cycle)
        df_out["doy_sin"] = np.sin(2.0 * np.pi * doy / 365.25)
        df_out["doy_cos"] = np.cos(2.0 * np.pi * doy / 365.25)

        df_out["month"] = month.astype(int)
        return df_out

    def build_feature_matrix(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = "target_min_do_72h",
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Builds complete leakage-free feature matrix.

        Returns:
            Tuple of (DataFrame with features and target, list of feature column names).
        """
        df_feat = df.copy()

        # Ensure datetime index
        if "timestamp" in df_feat.columns and not isinstance(df_feat.index, pd.DatetimeIndex):
            df_feat["timestamp"] = pd.to_datetime(df_feat["timestamp"])
            df_feat = df_feat.set_index("timestamp")

        # Sort chronologically to guarantee correct shifting and rolling
        df_feat = df_feat.sort_index()

        # 1. Physical saturation features
        if self.config.get("include_physical_saturation", True):
            df_feat = self.add_physical_saturation_features(df_feat)

        # 2. Lag features
        df_feat = self.add_lag_features(df_feat)

        # 3. Rolling backward statistics
        df_feat = self.add_rolling_backward_features(df_feat)

        # 4. Change features
        df_feat = self.add_change_features(df_feat)

        # 5. Cyclical seasonal features
        if self.config.get("include_diurnal", True) or self.config.get("include_annual", True):
            df_feat = self.add_cyclical_seasonal_features(df_feat)

        # Identify all engineered feature columns
        # Exclude qualifiers, target, and raw non-feature columns
        exclude_cols = {
            "timestamp",
            target_col,
            "water_temperature_qualifiers",
            "discharge_qualifiers",
            "gage_height_qualifiers",
            "dissolved_oxygen_qualifiers",
            "turbidity_qualifiers",
            "gage_height",  # gage height is redundant with discharge
        }
        feature_cols = [c for c in df_feat.columns if c not in exclude_cols and not c.endswith("_qualifiers")]

        logger.info(
            "Built feature matrix with %d samples and %d engineered features.",
            len(df_feat),
            len(feature_cols),
        )
        return df_feat, feature_cols
