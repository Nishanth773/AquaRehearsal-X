"""
AquaRehearsal-X - Stratified Uncertainty & Boundary-Crossing Probability Engine
Stage 3: Resolving Static Calibration Deficit via Thermally Conditioned Uncertainty

Solves the key scientific caveat identified in Stage 2.5:
"Split-conformal intervals calibrated across annual averages underestimate warm-season
variance. Seasonally / thermally conditioned intervals are required for Stage 3."

Implements:
1. StratifiedUncertaintyCalibrator:
   - Partitions residuals by thermal regime (Cold <15°C, Moderate 15-22°C, Warm >=22°C).
   - Computes regime-specific conformal margins and effective dispersion parameters.
2. BoundaryCrossingProbability:
   - Computes the exact probability that future minimum DO will drop below:
     * 5.0 mg/L (Standard protection criterion)
     * 4.0 mg/L (Acute regulatory standard)
     * 2.0 mg/L (Severe hypoxia / fish kill threshold)
   - Categorizes risk into operational alert levels (NORMAL, ADVISORY, WARNING, EMERGENCY).
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

from src.config.stage3_settings import (
    STAGE3_REGULATORY_THRESHOLDS,
    EARLY_WARNING_LEVELS,
    STAGE3_MODELS_DIR,
)
from src.utils.logger import logger


class StratifiedUncertaintyCalibrator:
    """
    Calibrates regime-specific conformal prediction intervals and residual dispersions
    stratified across thermal regimes to account for heightened warm-season volatility.
    """

    def __init__(self, target_coverage: float = 0.80):
        self.target_coverage = target_coverage
        self.alpha = 1.0 - target_coverage
        self.regime_stats: Dict[str, Dict[str, float]] = {
            "cold": {"conformal_margin": 1.15, "sigma": 0.88, "n_samples": 0},
            "moderate": {"conformal_margin": 1.35, "sigma": 1.02, "n_samples": 0},
            "warm": {"conformal_margin": 1.82, "sigma": 1.41, "n_samples": 0},
        }

    def fit_from_residuals(
        self,
        y_true: pd.Series,
        y_pred: pd.Series,
        temperatures: pd.Series,
    ) -> Dict[str, Dict[str, float]]:
        """
        Fits stratified non-conformity quantiles and dispersion parameters
        from validation actuals, predictions, and water temperatures.
        """
        residuals = y_true.values - y_pred.values
        abs_residuals = np.abs(residuals)
        temps = temperatures.values

        for regime, (t_min, t_max) in [("cold", (-10.0, 15.0)), ("moderate", (15.0, 22.0)), ("warm", (22.0, 50.0))]:
            mask = (temps >= t_min) & (temps < t_max) & (~np.isnan(residuals))
            n = int(np.sum(mask))
            if n > 15:
                reg_abs_res = abs_residuals[mask]
                reg_res = residuals[mask]
                # Conformal quantile using finite-sample correction
                q_level = min(1.0, np.ceil((n + 1) * (1.0 - self.alpha)) / n)
                margin = float(np.quantile(reg_abs_res, q_level))
                sigma = float(np.std(reg_res, ddof=1))
                self.regime_stats[regime] = {
                    "conformal_margin": round(margin, 3),
                    "sigma": round(sigma, 3),
                    "n_samples": n,
                }
                logger.info(
                    "Calibrated %s regime: n=%d, conformal_margin=%.3f, sigma=%.3f",
                    regime, n, margin, sigma
                )
            else:
                logger.warning("Insufficient samples (%d) in %s regime; retaining baseline.", n, regime)

        return self.regime_stats

    def evaluate_test_coverage(
        self,
        y_true_test: pd.Series,
        y_pred_test: pd.Series,
        temps_test: pd.Series,
    ) -> Dict[str, Dict[str, float]]:
        """Evaluates empirical coverage of the stratified intervals on unseen test data."""
        coverage_results = {}
        for regime, (t_min, t_max) in [("cold", (-10.0, 15.0)), ("moderate", (15.0, 22.0)), ("warm", (22.0, 50.0))]:
            mask = (temps_test >= t_min) & (temps_test < t_max) & (~np.isnan(y_true_test))
            n = int(np.sum(mask))
            if n > 0:
                y_t = y_true_test.values[mask]
                y_p = y_pred_test.values[mask]
                margin = self.regime_stats[regime]["conformal_margin"]
                lower = y_p - margin
                upper = y_p + margin
                covered = (y_t >= lower) & (y_t <= upper)
                cov_pct = float(np.mean(covered) * 100.0)
                coverage_results[regime] = {
                    "empirical_coverage_pct": round(cov_pct, 2),
                    "nominal_target_pct": round(self.target_coverage * 100.0, 1),
                    "interval_width_mg_L": round(2 * margin, 3),
                    "test_samples": n,
                }
            else:
                coverage_results[regime] = {"test_samples": 0}
        return coverage_results

    def save(self, filepath: Path):
        """Saves calibration dictionary to JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.regime_stats, f, indent=2)
        logger.info("Saved stratified uncertainty calibration to %s", filepath)

    @classmethod
    def load(cls, filepath: Path) -> "StratifiedUncertaintyCalibrator":
        """Loads calibration dictionary from JSON."""
        instance = cls()
        if Path(filepath).exists():
            with open(filepath, "r", encoding="utf-8") as f:
                instance.regime_stats = json.load(f)
            logger.info("Loaded stratified uncertainty calibration from %s", filepath)
        return instance


class BoundaryCrossingProbability:
    """
    Computes boundary-crossing probabilities P(DO_min < tau) and assigns operational alert levels.
    """

    def __init__(self, calibrator: Optional[StratifiedUncertaintyCalibrator] = None):
        self.calibrator = calibrator or StratifiedUncertaintyCalibrator()
        self.thresholds = STAGE3_REGULATORY_THRESHOLDS
        self.alert_levels = EARLY_WARNING_LEVELS

    def get_dispersion_for_temperature(self, temp_c: float) -> Tuple[float, float]:
        """Returns (conformal_margin, sigma) for a given water temperature."""
        if temp_c < 15.0:
            stats = self.calibrator.regime_stats.get("cold", {"conformal_margin": 1.15, "sigma": 0.88})
        elif temp_c < 22.0:
            stats = self.calibrator.regime_stats.get("moderate", {"conformal_margin": 1.35, "sigma": 1.02})
        else:
            stats = self.calibrator.regime_stats.get("warm", {"conformal_margin": 1.82, "sigma": 1.41})
        return stats["conformal_margin"], stats["sigma"]

    def compute_crossing_probabilities(
        self,
        expected_min_do: float,
        ambient_temp_c: float,
    ) -> Dict[str, float]:
        """
        Calculates P(DO_min < tau) for tau in {5.0, 4.0, 2.0} mg/L
        using the temperature-conditioned predictive dispersion.
        """
        _, sigma = self.get_dispersion_for_temperature(ambient_temp_c)
        sigma = max(0.20, sigma)

        # Normal cumulative distribution: P(Y < tau) = Phi((tau - mu) / sigma)
        p_std_5_0 = float(norm.cdf((self.thresholds["standard_protection"] - expected_min_do) / sigma))
        p_acute_4_0 = float(norm.cdf((self.thresholds["acute_stress"] - expected_min_do) / sigma))
        p_hypoxia_2_0 = float(norm.cdf((self.thresholds["severe_hypoxia"] - expected_min_do) / sigma))

        return {
            "p_crossing_standard_5_0": round(p_std_5_0, 4),
            "p_crossing_acute_4_0": round(p_acute_4_0, 4),
            "p_crossing_hypoxia_2_0": round(p_hypoxia_2_0, 4),
            "effective_dispersion_sigma": round(sigma, 3),
        }

    def compute_prediction_interval(
        self,
        expected_min_do: float,
        ambient_temp_c: float,
    ) -> Tuple[float, float]:
        """Returns 80% thermally conditioned prediction interval [lower, upper]."""
        margin, _ = self.get_dispersion_for_temperature(ambient_temp_c)
        lower = max(0.0, expected_min_do - margin)
        upper = expected_min_do + margin
        return round(float(lower), 2), round(float(upper), 2)

    def determine_alert_level(
        self,
        expected_min_do: float,
        p_acute_4_0: float,
        p_hypoxia_2_0: float,
    ) -> Dict[str, Any]:
        """
        Assigns structured operational early-warning alert level based on crossing probabilities.
        """
        if p_hypoxia_2_0 >= 0.20 or expected_min_do < 2.0 or p_acute_4_0 >= 0.70:
            level_key = "EMERGENCY"
        elif p_acute_4_0 >= 0.35 or expected_min_do < 4.0:
            level_key = "WARNING"
        elif p_acute_4_0 >= 0.10 or expected_min_do < 5.0:
            level_key = "ADVISORY"
        else:
            level_key = "NORMAL"

        info = self.alert_levels[level_key].copy()
        info["key"] = level_key
        return info
