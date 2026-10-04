"""
AquaRehearsal-X - Stage 2.5 Storm and Precipitation Feature Engineering
Historical Depth + Real Precipitation Upgrade

Extracts explicit storm-related and precipitation features:
- rainfall_1h (current hourly rainfall)
- rolling rainfall sums: rainfall_3h, rainfall_6h, rainfall_12h, rainfall_24h, rainfall_48h, rainfall_72h
- rainfall intensity: maximum hourly rate over 6h and 24h
- rainfall change: rate of increase over 3h
- antecedent rainfall: 7-day cumulative precipitation
- hydrologic storm dynamics: discharge changes, surge ratios, and turbidity changes

Scientific Integrity Mandates:
- All features use ONLY observations available at or before prediction time t.
- Rolling windows look strictly backward (closed='right').
- Missing precipitation is NEVER silently converted or imputed as 0.0 mm. Gaps produce NaNs.
- Feature importance represents statistical predictive contribution, NOT physical causality.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.config.stage2_5_settings import STAGE2_5_STORM_FEATURE_CONFIG
from src.features.feature_builder import FeatureBuilder
from src.utils.logger import logger


class StormFeatureBuilder:
    """Extracts storm-specific precipitation and hydrologic features."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or STAGE2_5_STORM_FEATURE_CONFIG
        self.precip_col = self.config.get("precipitation_col", "precipitation_mm")
        self.rolling_windows = self.config.get("precip_rolling_windows", ["3h", "6h", "12h", "24h", "48h", "72h"])
        self.discharge_change_hours = self.config.get("discharge_change_hours", [1, 3, 6, 24])
        self.turbidity_change_hours = self.config.get("turbidity_change_hours", [6, 24])

    def add_precipitation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds liquid rain and total precipitation storm features.
        Preserves NaNs for unobserved/missing rainfall periods.
        """
        df_out = df.copy()

        # Check for liquid rain column (primary) or precipitation column
        rain_col = "rain_mm" if "rain_mm" in df_out.columns else ("precipitation_mm" if "precipitation_mm" in df_out.columns else None)
        if not rain_col:
            logger.warning("Neither 'rain_mm' nor 'precipitation_mm' found in DataFrame. Skipping storm rainfall features.")
            return df_out

        s_rain = df_out[rain_col]

        # 1. Base current-hour liquid rain (rain_1h)
        df_out["rain_1h"] = s_rain

        # 2. Backward rolling liquid rain sums
        # min_periods requires at least 80% valid data in window; gaps remain NaN
        for win in self.rolling_windows:
            win_int = int(win.replace("h", "").replace("H", ""))
            min_p = max(1, int(win_int * 0.8))
            df_out[f"rain_roll_{win}"] = s_rain.rolling(win, min_periods=min_p, closed="right").sum()

        # 3. Maximum recent rainfall intensity (peak 1h rate in past 6h and 24h)
        for i_win in ["6h", "24h"]:
            i_win_int = int(i_win.replace("h", "").replace("H", ""))
            min_p = max(1, int(i_win_int * 0.8))
            df_out[f"rain_intensity_max_{i_win}"] = s_rain.rolling(i_win, min_periods=min_p, closed="right").max()

        # 4. Rainfall rate of change (3h change: R(t) - R(t - 3h))
        df_out["rain_change_3h"] = s_rain - s_rain.shift(3)

        # 5. Antecedent liquid rainfall: 7-day cumulative rainfall prior to prediction time
        # min_periods requires at least 134 valid hours out of 168 (80%)
        df_out["antecedent_rain_7d"] = s_rain.rolling("168h", min_periods=134, closed="right").sum()

        # Also preserve total precipitation features if precipitation_mm is distinct from rain_mm
        if "precipitation_mm" in df_out.columns and rain_col != "precipitation_mm":
            s_precip = df_out["precipitation_mm"]
            df_out["precipitation_1h"] = s_precip
            df_out["precipitation_roll_24h"] = s_precip.rolling("24h", min_periods=19, closed="right").sum()

        return df_out

    def add_storm_hydrologic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds discharge surge and turbidity response features.
        """
        df_out = df.copy()

        # Discharge changes and surge ratios
        if "discharge" in df_out.columns:
            q = df_out["discharge"]
            for h in self.discharge_change_hours:
                lagged_q = q.shift(h)
                df_out[f"discharge_change_{h}h"] = q - lagged_q
                df_out[f"discharge_surge_ratio_{h}h"] = (q - lagged_q) / np.clip(lagged_q, 1.0, None)

        # Turbidity changes
        if "turbidity" in df_out.columns:
            turb = df_out["turbidity"]
            for h in self.turbidity_change_hours:
                df_out[f"turbidity_change_{h}h"] = turb - turb.shift(h)

        return df_out

    def build_model_feature_matrices(
        self,
        df: pd.DataFrame,
        target_col: str = "target_min_do_72h",
    ) -> Tuple[pd.DataFrame, List[str], List[str]]:
        """
        Builds both feature matrices:
        - MODEL A: Water-Only features (DO, Temp, Discharge, Turbidity, Lags, Rolling Stats, Seasonality)
        - MODEL B: Water + Precipitation features (Model A features + Storm Rainfall features)

        Returns:
            Tuple of:
            - DataFrame containing all features and target
            - List of Model A feature column names (water-only)
            - List of Model B feature column names (water + precipitation)
        """
        # 1. First build base water features using FeatureBuilder
        base_builder = FeatureBuilder()
        df_feats, base_water_cols = base_builder.build_feature_matrix(df, target_col=target_col)

        # 2. Add storm & precipitation features
        df_storm = self.add_precipitation_features(df_feats)
        df_storm = self.add_storm_hydrologic_features(df_storm)

        # Exclude metadata, target, qualifiers, and raw non-feature columns
        exclude_cols = {
            "timestamp",
            target_col,
            "water_temperature_qualifiers",
            "discharge_qualifiers",
            "gage_height_qualifiers",
            "dissolved_oxygen_qualifiers",
            "turbidity_qualifiers",
            "gage_height",
            "precipitation_mm",
            "rain_mm",
        }

        # Model A features: strictly water and seasonal features (no rainfall features)
        precip_feature_prefixes = ("rain_", "precipitation_", "antecedent_rain_")
        model_a_features = [
            c for c in base_water_cols
            if not any(c.startswith(p) for p in precip_feature_prefixes)
            and c not in exclude_cols
        ]

        # Model B features: Model A features PLUS all storm and precipitation features
        all_candidate_cols = [c for c in df_storm.columns if c not in exclude_cols and not c.endswith("_qualifiers")]
        model_b_features = all_candidate_cols

        logger.info(
            "Built feature matrices: Model A (Water-Only) = %d features; Model B (Water + Precip) = %d features.",
            len(model_a_features),
            len(model_b_features),
        )

        return df_storm, model_a_features, model_b_features
