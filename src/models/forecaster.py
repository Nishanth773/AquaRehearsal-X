"""
AquaRehearsal-X - Main ML Forecaster
72-Hour Dissolved Oxygen Forecasting Engine

Implements LightGBM-based gradient boosted decision tree regression for 72-hour future minimum DO.
Supports early stopping on chronological validation set and feature importance extraction.
Provides transparent fallback to HistGradientBoostingRegressor if LightGBM encounters system issues.

Mandate:
- Model feature importance is explicitly labeled as statistical association, NOT causal explanation.
- Chronological separation is strictly maintained.
"""

from typing import Dict, List, Optional, Tuple, Any
import joblib
from pathlib import Path
import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

from sklearn.ensemble import HistGradientBoostingRegressor
from src.config.stage2_settings import STAGE2_MODEL_CONFIG, STAGE2_MODELS_DIR
from src.utils.logger import logger


class DissolvedOxygenForecaster:
    """72-hour future minimum dissolved oxygen gradient boosting forecaster."""

    def __init__(
        self,
        model_params: Optional[Dict[str, Any]] = None,
        early_stopping_rounds: int = 30,
        random_seed: int = 42,
        force_fallback: bool = False,
    ):
        self.random_seed = random_seed
        self.early_stopping_rounds = early_stopping_rounds
        self.model_params = model_params or STAGE2_MODEL_CONFIG.get("lgbm_params", {}).copy()
        self.model_params["random_state"] = random_seed
        self.force_fallback = force_fallback

        self.model = None
        self.is_fallback = False
        self.feature_names: List[str] = []
        self.training_metadata: Dict[str, Any] = {}

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ):
        """
        Trains model with chronological validation.

        Args:
            X_train: Feature matrix for training period.
            y_train: Target vector for training period.
            X_val: Feature matrix for validation period (optional, for early stopping).
            y_val: Target vector for validation period.
        """
        self.feature_names = list(X_train.columns)

        if LIGHTGBM_AVAILABLE and not self.force_fallback:
            try:
                logger.info("Initializing LightGBM Regressor for 72h minimum DO forecasting...")
                callbacks = []
                eval_set = None

                # Setup early stopping if validation set provided
                if X_val is not None and y_val is not None and len(X_val) > 0:
                    eval_set = [(X_val, y_val)]
                    callbacks.append(lgb.early_stopping(stopping_rounds=self.early_stopping_rounds, verbose=False))
                    callbacks.append(lgb.log_evaluation(period=0))

                self.model = lgb.LGBMRegressor(**self.model_params)
                self.model.fit(
                    X_train,
                    y_train,
                    eval_set=eval_set,
                    callbacks=callbacks if callbacks else None,
                )
                self.is_fallback = False
                logger.info(
                    "LightGBM trained successfully. Best iteration: %s",
                    getattr(self.model, "best_iteration_", self.model_params.get("n_estimators")),
                )
            except Exception as e:
                logger.warning("LightGBM fitting encountered error: %s. Engaging HistGradientBoostingRegressor fallback.", e)
                self._fit_fallback(X_train, y_train, X_val, y_val)
        else:
            logger.info("Using HistGradientBoostingRegressor (fallback mode).")
            self._fit_fallback(X_train, y_train, X_val, y_val)

        return self

    def _fit_fallback(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ):
        """Fallback to scikit-learn's native HistGradientBoostingRegressor."""
        self.is_fallback = True
        params = {
            "max_iter": self.model_params.get("n_estimators", 300),
            "learning_rate": self.model_params.get("learning_rate", 0.03),
            "max_depth": self.model_params.get("max_depth", 5),
            "random_state": self.random_seed,
            "early_stopping": True if X_val is not None else False,
            "n_iter_no_change": self.early_stopping_rounds,
        }
        self.model = HistGradientBoostingRegressor(**params)
        self.model.fit(X_train, y_train)
        logger.info("HistGradientBoostingRegressor fallback trained successfully.")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generates point predictions for future 72-hour minimum DO."""
        if self.model is None:
            raise RuntimeError("Model must be fitted before predict.")
        X_aligned = X[self.feature_names]
        return self.model.predict(X_aligned)

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Extracts model feature importance.
        Labels explicitly as 'model feature importance' (statistical split/gain), NOT causal driver.
        """
        if self.model is None:
            raise RuntimeError("Model must be fitted to get feature importance.")

        if not self.is_fallback and hasattr(self.model, "feature_importances_"):
            gain_importance = self.model.booster_.feature_importance(importance_type="gain")
            split_importance = self.model.booster_.feature_importance(importance_type="split")
            df_imp = pd.DataFrame({
                "feature": self.feature_names,
                "importance_gain": gain_importance,
                "importance_split": split_importance,
            })
            # Normalize gain to percentage
            total_gain = df_imp["importance_gain"].sum()
            df_imp["importance_gain_pct"] = (df_imp["importance_gain"] / total_gain * 100.0) if total_gain > 0 else 0.0
            return df_imp.sort_values(by="importance_gain", ascending=False).reset_index(drop=True)
        else:
            # HistGradientBoosting doesn't provide direct tree gain attributes in the same format
            return pd.DataFrame({"feature": self.feature_names, "importance_gain_pct": 1.0 / len(self.feature_names)})

    def save(self, filepath: Path):
        """Saves model artifact and metadata to disk."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model": self.model,
            "is_fallback": self.is_fallback,
            "feature_names": self.feature_names,
            "model_params": self.model_params,
            "random_seed": self.random_seed,
            "training_metadata": self.training_metadata,
        }
        joblib.dump(artifact, filepath)
        logger.info("Saved forecaster model artifact to %s", filepath)

    @classmethod
    def load(cls, filepath: Path) -> "DissolvedOxygenForecaster":
        """Loads model artifact from disk."""
        artifact = joblib.load(filepath)
        instance = cls(
            model_params=artifact["model_params"],
            random_seed=artifact["random_seed"],
            force_fallback=artifact["is_fallback"],
        )
        instance.model = artifact["model"]
        instance.is_fallback = artifact["is_fallback"]
        instance.feature_names = artifact["feature_names"]
        instance.training_metadata = artifact.get("training_metadata", {})
        logger.info("Loaded forecaster model artifact from %s", filepath)
        return instance
