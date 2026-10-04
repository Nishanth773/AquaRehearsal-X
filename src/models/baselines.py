"""
AquaRehearsal-X - Baseline Models
72-Hour Dissolved Oxygen Forecasting Engine

Implements transparent, non-ML baseline models for scientific comparison:
1. Baseline A (Persistence): Predicts future 72-hour minimum DO using the current/latest DO observation.
2. Baseline B (Linear / Seasonal): Fits a Ridge regression on current DO, water temperature,
   and seasonal / diurnal cyclical encodings strictly on training data.

Purpose:
To answer the core scientific question:
"Does the ML model provide useful predictive skill beyond simple information available at prediction time?"
"""

from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

from src.utils.logger import logger


class PersistenceBaseline:
    """
    Baseline A: Persistence.
    Predicts future 72h minimum DO = current DO observation.
    Requires no training / parameter fitting.
    """

    def __init__(self, current_do_col: str = "dissolved_oxygen"):
        self.current_do_col = current_do_col
        self.name = "Baseline A (Persistence: Current DO)"

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None):
        """No-op for persistence."""
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Returns the current dissolved oxygen column as predictions."""
        if self.current_do_col not in X.columns:
            raise KeyError(f"Current DO column '{self.current_do_col}' not found in input features.")
        return X[self.current_do_col].to_numpy(dtype=float)


class LinearSeasonalBaseline:
    """
    Baseline B: Current DO + Temperature + Seasonality.
    Fits a regularized Ridge regression strictly on training data using:
    - current DO
    - current water temperature
    - diurnal cycle (hour_sin, hour_cos)
    - annual cycle (doy_sin, doy_cos)
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.name = "Baseline B (Current DO + Temp + Season)"
        self.features = ["dissolved_oxygen", "water_temperature", "hour_sin", "hour_cos", "doy_sin", "doy_cos"]
        self.pipeline: Optional[Pipeline] = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        """Fits Ridge pipeline on training data."""
        available_features = [f for f in self.features if f in X.columns]
        if len(available_features) < 2:
            raise ValueError(f"Insufficient baseline features in input. Found: {available_features}")

        self.features = available_features
        X_sub = X[self.features].copy()

        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=self.alpha, random_state=42)),
        ])

        self.pipeline.fit(X_sub, y)
        logger.info(
            "Fitted Baseline B (%s) on %d samples with features: %s",
            self.name,
            len(X_sub),
            self.features,
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generates predictions using fitted pipeline."""
        if self.pipeline is None:
            raise RuntimeError("Baseline B model must be fitted before predict.")
        X_sub = X[self.features].copy()
        return self.pipeline.predict(X_sub)
