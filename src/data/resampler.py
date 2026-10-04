"""
AquaRehearsal-X - Configurable Temporal Resampling Layer
Stage 1: Real Data Foundation

Preserves native temporal resolution while offering flexible, scientifically
defensible resampling to standard intervals (15-min, hourly, daily).
"""

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from src.config.settings import RESAMPLING_CONFIG
from src.utils.logger import logger


class DataResampler:
    """Detects native temporal resolution and supports multi-scale resampling."""

    @staticmethod
    def detect_native_resolution(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes the time deltas between consecutive observations to determine
        the native frequency and regularity of the sensor measurements.
        """
        if df.empty or len(df) < 2:
            return {
                "native_frequency": "unknown",
                "median_interval_minutes": None,
                "min_interval_minutes": None,
                "max_interval_minutes": None,
                "is_regular": False,
                "observation_count": len(df),
            }

        # Calculate time differences in minutes
        deltas = df.index.to_series().diff().dropna().dt.total_seconds() / 60.0
        median_delta = float(deltas.median())
        min_delta = float(deltas.min())
        max_delta = float(deltas.max())
        std_delta = float(deltas.std())

        # Classify typical nominal frequency
        if 13 <= median_delta <= 17:
            nominal_freq = "15-minute"
            freq_str = "15min"
        elif 55 <= median_delta <= 65:
            nominal_freq = "hourly"
            freq_str = "1h"
        elif 1400 <= median_delta <= 1480:
            nominal_freq = "daily"
            freq_str = "1d"
        else:
            nominal_freq = f"custom_{round(median_delta, 1)}min"
            freq_str = f"{round(median_delta)}min"

        # Check regularity: is 90% of intervals within 10% of median?
        regular_count = ((deltas >= median_delta * 0.9) & (deltas <= median_delta * 1.1)).sum()
        is_regular = bool((regular_count / len(deltas)) >= 0.90)

        result = {
            "native_frequency": nominal_freq,
            "pandas_freq_str": freq_str,
            "median_interval_minutes": round(median_delta, 2),
            "min_interval_minutes": round(min_delta, 2),
            "max_interval_minutes": round(max_delta, 2),
            "std_interval_minutes": round(std_delta, 2),
            "is_regular": is_regular,
            "observation_count": len(df),
        }
        logger.info(
            "Detected native resolution: %s (median: %.1f min, regular: %s, total obs: %d)",
            nominal_freq,
            median_delta,
            is_regular,
            len(df),
        )
        return result

    @staticmethod
    def resample(
        df: pd.DataFrame,
        target_resolution: str = "native",
        agg_methods: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Resamples time series data to the requested resolution.

        Args:
            df: DataFrame with UTC DatetimeIndex
            target_resolution: 'native', '15min', '1h', '1d' (case-insensitive)
            agg_methods: Mapping of column names to aggregation functions ('mean', 'min', 'max')

        Returns:
            Resampled DataFrame with preserved column structure.
        """
        if df.empty or target_resolution.lower() == "native":
            return df.copy()

        # Map user strings to valid pandas frequency strings
        freq_mapping = {
            "15min": "15min",
            "15m": "15min",
            "15t": "15min",
            "1h": "1h",
            "hourly": "1h",
            "1d": "1D",
            "daily": "1D",
        }
        pandas_rule = freq_mapping.get(target_resolution.lower())
        if not pandas_rule:
            raise ValueError(
                f"Unsupported target resolution '{target_resolution}'. "
                f"Supported: {list(freq_mapping.keys())} or 'native'."
            )

        if agg_methods is None:
            agg_methods = RESAMPLING_CONFIG.get("aggregations", {})

        # Resample numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        agg_dict = {col: agg_methods.get(col, "mean") for col in numeric_cols}

        logger.info("Resampling series from native resolution to '%s'...", pandas_rule)
        resampled_numeric = df[numeric_cols].resample(pandas_rule).agg(agg_dict)

        # For qualifiers / non-numeric, aggregate by joining unique non-null values
        non_numeric_cols = [c for c in df.columns if c not in numeric_cols]
        if non_numeric_cols:
            def combine_qualifiers(series):
                valid = series.dropna().unique()
                return ";".join(str(x) for x in valid) if len(valid) > 0 else np.nan

            resampled_non_numeric = df[non_numeric_cols].resample(pandas_rule).apply(combine_qualifiers)
            return resampled_numeric.join(resampled_non_numeric)

        return resampled_numeric
