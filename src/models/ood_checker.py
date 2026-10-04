"""
AquaRehearsal-X - Out-of-Distribution Checker
72-Hour Dissolved Oxygen Forecasting Engine

Implements a basic input-domain warning mechanism to detect when new sensor inputs
are substantially outside the historical training data distribution.

CRITICAL SCIENTIFIC DISCLAIMER:
- This is strictly a 'Basic input-domain warning', NOT a definitive safety mechanism or formal OOD detector.
- It detects univariate range and statistical envelope excursions (e.g. historical maximum discharge exceeded).
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import numpy as np
import pandas as pd

from src.utils.logger import logger


class InputDomainChecker:
    """Basic input-domain warning detector based on training data distributions."""

    def __init__(self, key_variables: Optional[List[str]] = None, n_std_threshold: float = 3.5):
        self.key_variables = key_variables or [
            "dissolved_oxygen",
            "water_temperature",
            "discharge",
            "turbidity",
        ]
        self.n_std_threshold = n_std_threshold
        self.domain_stats: Dict[str, Dict[str, float]] = {}

    def fit(self, X_train: pd.DataFrame):
        """Learns distribution bounds strictly from the training dataset."""
        self.domain_stats = {}
        for col in X_train.columns:
            if col in self.key_variables or any(k in col for k in self.key_variables):
                series = X_train[col].dropna()
                if len(series) == 0:
                    continue
                self.domain_stats[col] = {
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "mean": float(series.mean()),
                    "std": float(series.std()) if len(series) > 1 else 0.0,
                    "p01": float(np.percentile(series, 1)),
                    "p99": float(np.percentile(series, 99)),
                }

        logger.info(
            "Fitted basic input-domain checker across %d variables strictly on training data.",
            len(self.domain_stats),
        )
        return self

    def check_sample(self, input_features: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluates a single prediction input against training bounds.

        Returns:
            Dict containing warning flag, list of flagged variables, and detailed explanations.
        """
        flagged = []
        details = []

        for var, stats in self.domain_stats.items():
            if var in input_features:
                val = input_features[var]
                if val is None or np.isnan(val):
                    continue

                min_val = stats["min"]
                max_val = stats["max"]
                mean_val = stats["mean"]
                std_val = stats["std"]

                # Check strict range violation
                if val < min_val:
                    flagged.append(var)
                    details.append(
                        f"'{var}' ({val:.2f}) is below historical training minimum ({min_val:.2f})."
                    )
                elif val > max_val:
                    flagged.append(var)
                    details.append(
                        f"'{var}' ({val:.2f}) exceeds historical training maximum ({max_val:.2f})."
                    )
                # Check extreme statistical deviation
                elif std_val > 0 and abs(val - mean_val) > (self.n_std_threshold * std_val):
                    flagged.append(var)
                    details.append(
                        f"'{var}' ({val:.2f}) is >{self.n_std_threshold} standard deviations from training mean."
                    )

        has_warning = len(flagged) > 0
        return {
            "has_domain_warning": has_warning,
            "warning_type": "Basic input-domain warning" if has_warning else None,
            "flagged_variables": flagged,
            "details": details,
            "disclaimer": (
                "Basic input-domain warning: Inputs fall outside observed training bounds. "
                "Forecast confidence is degraded." if has_warning else "Inputs within observed training bounds."
            ),
        }

    def save(self, filepath: Path):
        """Saves domain statistics to JSON."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.domain_stats, f, indent=2)
        logger.info("Saved input domain stats to %s", filepath)

    @classmethod
    def load(cls, filepath: Path) -> "InputDomainChecker":
        """Loads domain statistics from JSON."""
        instance = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            instance.domain_stats = json.load(f)
        logger.info("Loaded input domain stats from %s", filepath)
        return instance
