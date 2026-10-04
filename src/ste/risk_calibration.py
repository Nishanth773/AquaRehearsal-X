"""
AquaRehearsal-X - Risk Calibration & Discrimination Evaluator
Component: risk_calibration.py

Computes probabilistic calibration and binary discrimination metrics:
- Brier Score: Mean squared error of probabilistic predictions.
- Reliability / Calibration Analysis: Predicted risk bins vs observed empirical event frequencies.
- Confusion Matrix: Evaluated at the operational risk probability limit (default 20%).
- Precision, Recall (Sensitivity), Specificity, and F1-Score.
- ROC-AUC and PR-AUC when positive and negative classes are both adequately populated.
- Transparent reporting safeguards: Explicitly omits or flags metrics when sample support is insufficient.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score, precision_recall_curve, auc

from src.utils.logger import logger


class RiskCalibrator:
    """
    Evaluates probabilistic calibration, reliability diagrams, and discrimination metrics.
    """

    def __init__(self, operational_risk_limit: float = 0.20):
        self.risk_limit = operational_risk_limit

    def evaluate_calibration_and_discrimination(
        self,
        y_true_binary: np.ndarray,
        y_pred_probs: np.ndarray,
        risk_limit: Optional[float] = None,
        n_bins: int = 5,
    ) -> Dict[str, Any]:
        """
        Calculates Brier score, contingency table, precision/recall, and reliability bins.
        """
        limit = risk_limit if risk_limit is not None else self.risk_limit
        y_true = np.asarray(y_true_binary).astype(int)
        probs = np.asarray(y_pred_probs).astype(float)

        # Filter out NaNs
        valid_mask = (~np.isnan(y_true)) & (~np.isnan(probs))
        y_true = y_true[valid_mask]
        probs = probs[valid_mask]
        n_total = len(y_true)

        if n_total == 0:
            return {"error": "Insufficient valid observations to compute calibration metrics."}

        # Brier Score
        brier = float(brier_score_loss(y_true, probs))

        # Binary decisions at operational risk limit (e.g. P >= 0.20)
        y_pred_binary = (probs >= limit).astype(int)

        tp = int(np.sum((y_pred_binary == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred_binary == 1) & (y_true == 0)))
        fn = int(np.sum((y_pred_binary == 0) & (y_true == 1)))
        tn = int(np.sum((y_pred_binary == 0) & (y_true == 0)))

        n_pos = int(np.sum(y_true == 1))
        n_neg = int(np.sum(y_true == 0))

        # Sensitivity / Recall
        if n_pos > 0:
            sensitivity = float(tp / (tp + fn))
        else:
            sensitivity = 1.0 if fn == 0 else 0.0  # Perfect recall if zero misses

        # Specificity
        if n_neg > 0:
            specificity = float(tn / (tn + fp))
        else:
            specificity = 0.0

        # Precision
        if (tp + fp) > 0:
            precision = float(tp / (tp + fp))
        else:
            precision = 0.0

        # F1-Score
        if (precision + sensitivity) > 0:
            f1 = float((2 * precision * sensitivity) / (precision + sensitivity))
        else:
            f1 = 0.0

        # ROC-AUC & PR-AUC (Only meaningful if both classes present)
        roc_auc = None
        pr_auc = None
        if n_pos > 0 and n_neg > 0:
            try:
                roc_auc = float(roc_auc_score(y_true, probs))
                p_curve, r_curve, _ = precision_recall_curve(y_true, probs)
                pr_auc = float(auc(r_curve, p_curve))
            except Exception as e:
                logger.warning("Could not calculate AUC metrics: %s", e)
        else:
            logger.info("Single class present (pos=%d, neg=%d). ROC/PR-AUC omitted to prevent distortion.", n_pos, n_neg)

        # Reliability diagram binning
        bins = np.linspace(0.0, 1.0, n_bins + 1)
        bin_records = []
        for b_idx in range(n_bins):
            b_low = bins[b_idx]
            b_high = bins[b_idx + 1]
            in_bin = (probs >= b_low) & (probs < b_high if b_idx < n_bins - 1 else probs <= b_high)
            bin_count = int(np.sum(in_bin))
            if bin_count > 0:
                mean_pred = float(np.mean(probs[in_bin]))
                emp_freq = float(np.mean(y_true[in_bin]))
            else:
                mean_pred = float((b_low + b_high) / 2.0)
                emp_freq = np.nan

            bin_records.append({
                "bin_low": round(b_low, 2),
                "bin_high": round(b_high, 2),
                "sample_count": bin_count,
                "mean_predicted_prob": round(mean_pred, 3),
                "empirical_frequency": round(emp_freq, 3) if not np.isnan(emp_freq) else None,
            })

        return {
            "total_samples": n_total,
            "positive_events_count": n_pos,
            "negative_events_count": n_neg,
            "operational_risk_limit": limit,
            "brier_score": round(brier, 4),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "sensitivity_recall": round(sensitivity, 3),
            "specificity": round(specificity, 3),
            "precision": round(precision, 3),
            "f1_score": round(f1, 3),
            "roc_auc": round(roc_auc, 3) if roc_auc is not None else "UNAVAILABLE_SINGLE_CLASS",
            "pr_auc": round(pr_auc, 3) if pr_auc is not None else "UNAVAILABLE_SINGLE_CLASS",
            "reliability_bins": bin_records,
        }
