"""
AquaRehearsal-X - Prediction API Interface
72-Hour Dissolved Oxygen Forecasting Engine

Provides clean, structured programmatic interface for generating future 72-hour
minimum dissolved oxygen forecasts with uncertainty bounds and input-domain checks.

Usage:
    result = predict_min_do(input_features)
"""

from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import json
import numpy as np
import pandas as pd

from src.config.stage2_settings import STAGE2_MODELS_DIR, STAGE2_STATION_CONFIG
from src.models.forecaster import DissolvedOxygenForecaster
from src.models.uncertainty import QuantileForecaster, SplitConformalCalibrator
from src.models.ood_checker import InputDomainChecker
from src.utils.logger import logger


class AquaForecastingAPI:
    """Encapsulates model artifacts and exposes structured inference API."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir or STAGE2_MODELS_DIR)
        self.forecaster: Optional[DissolvedOxygenForecaster] = None
        self.quantile_forecaster: Optional[QuantileForecaster] = None
        self.domain_checker: Optional[InputDomainChecker] = None
        self.metadata: Dict[str, Any] = {}
        self._load_artifacts()

    def _load_artifacts(self):
        """Loads fitted model artifacts and metadata from disk."""
        forecaster_path = self.models_dir / "lgbm_regressor.joblib"
        if forecaster_path.exists():
            self.forecaster = DissolvedOxygenForecaster.load(forecaster_path)
            logger.info("API loaded forecaster from %s", forecaster_path)

        domain_path = self.models_dir / "domain_ranges.json"
        if domain_path.exists():
            self.domain_checker = InputDomainChecker.load(domain_path)
            logger.info("API loaded domain ranges from %s", domain_path)

        metadata_path = self.models_dir / "model_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

        # Load quantile models if present
        q_models = {}
        for q_val in [10, 50, 90]:
            q_path = self.models_dir / f"lgbm_quantile_{q_val:02d}.joblib"
            if q_path.exists():
                import joblib
                q_art = joblib.load(q_path)
                q_models[q_val / 100.0] = q_art["model"]

        if q_models:
            self.quantile_forecaster = QuantileForecaster(quantiles=list(q_models.keys()))
            self.quantile_forecaster.models = q_models
            if self.forecaster:
                self.quantile_forecaster.feature_names = self.forecaster.feature_names
            logger.info("API loaded %d quantile models.", len(q_models))

    def predict(
        self,
        input_features: Union[Dict[str, Any], pd.Series, pd.DataFrame],
    ) -> Dict[str, Any]:
        """
        Generates 72-hour future minimum dissolved oxygen forecast.

        Args:
            input_features: Dict, Series, or single-row DataFrame containing feature values.

        Returns:
            Structured dictionary with point prediction, uncertainty bounds, and domain warning.
        """
        if self.forecaster is None:
            raise RuntimeError("API forecaster model is not loaded. Train model or verify path.")

        # Format input into a DataFrame
        if isinstance(input_features, dict):
            input_dict = input_features.copy()
            df_in = pd.DataFrame([input_dict])
        elif isinstance(input_features, pd.Series):
            input_dict = input_features.to_dict()
            df_in = pd.DataFrame([input_dict])
        elif isinstance(input_features, pd.DataFrame):
            df_in = input_features.copy()
            input_dict = df_in.iloc[0].to_dict()
        else:
            raise TypeError(f"Unsupported input type: {type(input_features)}")

        # Ensure all required features are present (reindex cleanly fills missing with NaN)
        df_aligned = df_in.reindex(columns=self.forecaster.feature_names)

        # 1. Domain / OOD Check
        domain_check = {"has_domain_warning": False, "details": []}
        if self.domain_checker is not None:
            domain_check = self.domain_checker.check_sample(input_dict)

        # 2. Point Prediction
        point_pred = float(self.forecaster.predict(df_aligned)[0])

        # 3. Uncertainty Quantile Predictions
        lower_pred, upper_pred, median_pred = None, None, None
        if self.quantile_forecaster is not None:
            q_preds = self.quantile_forecaster.predict(df_aligned)
            if "q_0.10" in q_preds:
                lower_pred = float(q_preds["q_0.10"].iloc[0])
            if "q_0.50" in q_preds:
                median_pred = float(q_preds["q_0.50"].iloc[0])
            if "q_0.90" in q_preds:
                upper_pred = float(q_preds["q_0.90"].iloc[0])

        # Assemble structured output
        return {
            "target": "minimum_dissolved_oxygen_next_72h",
            "unit": "mg/L",
            "forecast_horizon_hours": 72,
            "point_forecast_mg_L": round(point_pred, 2),
            "median_forecast_mg_L": round(median_pred, 2) if median_pred is not None else None,
            "lower_bound_10th_percentile_mg_L": round(lower_pred, 2) if lower_pred is not None else None,
            "upper_bound_90th_percentile_mg_L": round(upper_pred, 2) if upper_pred is not None else None,
            "uncertainty_interval": "80% quantile prediction interval [q10, q90]",
            "domain_warning": domain_check,
            "model_metadata": {
                "station_id": self.metadata.get("station_id", STAGE2_STATION_CONFIG["primary_station_id"]),
                "station_name": self.metadata.get("station_name", STAGE2_STATION_CONFIG["primary_station_name"]),
                "model_type": "LightGBM Regressor (Quantile Ensembles)" if not self.forecaster.is_fallback else "HistGradientBoosting (Fallback)",
                "random_seed": self.forecaster.random_seed,
                "disclaimer": (
                    "AquaRehearsal-X Stage 2 site-specific prototype. "
                    "Predictions represent statistical associations, NOT deterministic causal projections. "
                    "Do NOT extrapolate outside the Schuylkill River catchment."
                ),
            },
        }


# Singleton API instance
_GLOBAL_API: Optional[AquaForecastingAPI] = None


def predict_min_do(
    input_features: Union[Dict[str, Any], pd.Series, pd.DataFrame],
    models_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Public functional interface for generating 72-hour future minimum DO forecasts.

    Args:
        input_features: Dictionary or Series of environmental sensor observations and features.
        models_dir: Optional custom path to model artifacts directory.

    Returns:
        Structured forecast dictionary.
    """
    global _GLOBAL_API
    if _GLOBAL_API is None or models_dir is not None:
        _GLOBAL_API = AquaForecastingAPI(models_dir=models_dir)
    return _GLOBAL_API.predict(input_features)
