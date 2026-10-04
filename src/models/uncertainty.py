"""
AquaRehearsal-X - Uncertainty Architecture
72-Hour Dissolved Oxygen Forecasting Engine

Implements two complementary uncertainty quantification approaches:
1. Quantile LightGBM: Pinball loss regression producing conditional quantile estimates:
   - 10th percentile: Lower bound (conservative risk scenario for ecological DO depletion)
   - 50th percentile: Conditional median
   - 90th percentile: Upper bound
   Forms an 80% prediction interval [q10, q90].

2. Split Conformal Prediction Calibrator:
   Calibrates prediction intervals using absolute residuals on the chronological validation set.
   Calculates empirical coverage on unseen test data.

Scientific Rigor & Limitations:
- These are 'prediction intervals' / 'quantile predictions', NOT classical Gaussian 'confidence intervals'.
- Standard conformal prediction assumes exchangeability (i.i.d.), which is violated by time-series autocorrelation.
  Empirical coverage must be verified and reported on out-of-sample data.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import joblib
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


class QuantileForecaster:
    """Trains separate quantile regression models for uncertainty estimation."""

    def __init__(
        self,
        quantiles: Optional[List[float]] = None,
        base_params: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
    ):
        self.quantiles = quantiles or STAGE2_MODEL_CONFIG.get("uncertainty_quantiles", [0.10, 0.50, 0.90])
        self.random_seed = random_seed
        self.base_params = base_params or STAGE2_MODEL_CONFIG.get("lgbm_params", {}).copy()
        self.models: Dict[float, Any] = {}
        self.feature_names: List[str] = []

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series):
        """Fits a quantile regression model for each specified quantile."""
        self.feature_names = list(X_train.columns)

        for q in self.quantiles:
            logger.info("Fitting quantile regressor for alpha=%.2f...", q)
            if LIGHTGBM_AVAILABLE:
                q_params = self.base_params.copy()
                q_params["objective"] = "quantile"
                q_params["alpha"] = q
                q_params["metric"] = "quantile"
                q_params["random_state"] = self.random_seed

                model = lgb.LGBMRegressor(**q_params)
                model.fit(X_train, y_train)
                self.models[q] = model
            else:
                # Scikit-learn HistGradientBoostingRegressor quantile loss
                model = HistGradientBoostingRegressor(
                    loss="quantile",
                    quantile=q,
                    max_iter=self.base_params.get("n_estimators", 300),
                    learning_rate=self.base_params.get("learning_rate", 0.03),
                    random_state=self.random_seed,
                )
                model.fit(X_train, y_train)
                self.models[q] = model

        logger.info("Successfully fitted %d quantile models: %s", len(self.models), list(self.models.keys()))
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Generates quantile predictions.

        Returns:
            DataFrame with columns like ['q_0.10', 'q_0.50', 'q_0.90']
        """
        if not self.models:
            raise RuntimeError("Quantile models must be fitted before predict.")

        X_aligned = X[self.feature_names]
        preds = {}
        for q, model in sorted(self.models.items()):
            preds[f"q_{q:.2f}"] = model.predict(X_aligned)

        df_preds = pd.DataFrame(preds, index=X.index)

        # Enforce non-crossing heuristic (sort across quantiles for monotonicity)
        # In quantile regression, crossing can occasionally occur in tail regions
        q_cols = [f"q_{q:.2f}" for q in sorted(self.models.keys())]
        vals = df_preds[q_cols].values
        vals_sorted = np.sort(vals, axis=1)
        df_preds[q_cols] = vals_sorted

        return df_preds

    def save(self, directory: Path):
        """Saves quantile models to disk."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for q, model in self.models.items():
            filepath = directory / f"lgbm_quantile_{int(q * 100):02d}.joblib"
            joblib.dump({"model": model, "quantile": q, "feature_names": self.feature_names}, filepath)
        logger.info("Saved all quantile models to %s", directory)


class SplitConformalCalibrator:
    """
    Inductive split conformal prediction calibrator.
    Uses the chronological validation period as the calibration set.
    """

    def __init__(self, nominal_coverage: float = 0.80):
        self.nominal_coverage = nominal_coverage
        self.calibration_scores: Optional[np.ndarray] = None
        self.conformal_quantile_margin: Optional[float] = None

    def calibrate(self, y_val_true: np.ndarray, y_val_pred: np.ndarray):
        """
        Calibrates on chronological validation set residuals.
        Nonconformity score: s_i = |y_true - y_pred|
        """
        y_val_true = np.asarray(y_val_true, dtype=float)
        y_val_pred = np.asarray(y_val_pred, dtype=float)

        mask = np.isfinite(y_val_true) & np.isfinite(y_val_pred)
        scores = np.abs(y_val_true[mask] - y_val_pred[mask])
        self.calibration_scores = scores

        n = len(scores)
        if n == 0:
            raise ValueError("Calibration set has 0 valid samples.")

        # Conformal quantile level: ceil((n+1) * coverage) / n, capped at 1.0
        q_level = min(1.0, np.ceil((n + 1) * self.nominal_coverage) / n)
        self.conformal_quantile_margin = float(np.quantile(scores, q_level, method="higher"))

        logger.info(
            "Conformal calibration completed on n=%d samples. Nominal coverage: %.1f%%, margin: +/- %.3f mg/L",
            n,
            self.nominal_coverage * 100.0,
            self.conformal_quantile_margin,
        )
        return self

    def predict_interval(self, y_pred: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Constructs prediction intervals [y_pred - margin, y_pred + margin].
        Clamps lower bound at physical minimum 0.0 mg/L.
        """
        if self.conformal_quantile_margin is None:
            raise RuntimeError("Calibrator must be fitted before generating intervals.")

        y_pred = np.asarray(y_pred, dtype=float)
        lower = np.maximum(0.0, y_pred - self.conformal_quantile_margin)
        upper = y_pred + self.conformal_quantile_margin
        return lower, upper

    @staticmethod
    def evaluate_coverage(
        y_true: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
    ) -> Dict[str, float]:
        """
        Calculates empirical coverage and average interval width on unseen data.
        """
        y_true = np.asarray(y_true, dtype=float)
        lower = np.asarray(lower, dtype=float)
        upper = np.asarray(upper, dtype=float)

        mask = np.isfinite(y_true) & np.isfinite(lower) & np.isfinite(upper)
        if mask.sum() == 0:
            return {"coverage_pct": 0.0, "mean_width_mg_L": 0.0, "sample_count": 0}

        covered = (y_true[mask] >= lower[mask]) & (y_true[mask] <= upper[mask])
        coverage_pct = float(covered.mean() * 100.0)
        mean_width = float(np.mean(upper[mask] - lower[mask]))

        return {
            "coverage_pct": round(coverage_pct, 2),
            "mean_width_mg_L": round(mean_width, 3),
            "sample_count": int(mask.sum()),
        }
