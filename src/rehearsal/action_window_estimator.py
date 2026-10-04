"""
AquaRehearsal-X - Action Window Estimator
Stage 4: Risk-to-Action Decision Support

Quantifies the available operational window before dissolved oxygen falls below
a critical threshold during storm disturbance events.

Scientific Principles & Caveats:
1. The primary empirical model predicts an aggregated 72-hour minimum DO value (DO_min^72h).
   It does NOT provide a continuous deterministic countdown clock.
2. Timing estimates are derived from the empirical lag-to-nadir distribution observed across
   58 historical storm disturbances at USGS Station 01474500 (Schuylkill River at Philadelphia):
   - Median time to trough: 23.5 hours
   - Interquartile Range (IQR): 14.0 to 38.5 hours
   - Earliest plausible nadir: 7.0 hours
3. Crossing-time intervals are reported as:
   - Earliest plausible crossing time (conservative P10-P25 bound)
   - Median / central estimated crossing time (P50)
   - Latest plausible crossing time (P75-P90 bound)
   - Cumulative crossing probabilities within 6, 12, 24, 48, and 72 hours
4. Results are explicitly labeled as an "Estimated Action Window", NEVER as a guaranteed safe period.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config.stage4_settings import (
    ACTION_WINDOW_HORIZONS,
    FEASIBILITY_TIERS,
    SCIENTIFIC_SAFEGUARDS,
)
from src.utils.logger import logger


class ActionWindowEstimator:
    """
    Estimates the plausible action window and crossing time probabilities
    for an incoming storm disturbance.
    """

    def __init__(
        self,
        default_threshold_mg_L: float = 5.0,
        historical_nadir_median_hours: float = 23.5,
        historical_nadir_p10_hours: float = 10.0,
        historical_nadir_p90_hours: float = 46.0,
    ):
        self.threshold = default_threshold_mg_L
        self.t_nadir_median = historical_nadir_median_hours
        self.t_nadir_p10 = historical_nadir_p10_hours
        self.t_nadir_p90 = historical_nadir_p90_hours

    def estimate_action_window(
        self,
        pre_storm_water_temp_c: float,
        pre_storm_do_mg_L: float,
        pre_storm_discharge_cfs: float,
        storm_rain_mm: float,
        storm_duration_hours: float = 18.0,
        threshold_mg_L: Optional[float] = None,
        expected_min_do_72h: Optional[float] = None,
        prob_72h_crossing: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Estimates the operational action window before a possible DO threshold breach.

        Returns:
            Dictionary containing earliest, median, latest crossing times,
            cumulative probabilities across horizons (6, 12, 24, 48, 72h),
            and explicit scientific caveats.
        """
        thr = float(threshold_mg_L if threshold_mg_L is not None else self.threshold)

        # 1. Refusal check for missing or unphysical inputs
        if pre_storm_water_temp_c is None or np.isnan(pre_storm_water_temp_c):
            return self._build_refusal("Missing pre-storm water temperature.")
        if storm_rain_mm is None or np.isnan(storm_rain_mm):
            return self._build_refusal("Missing storm rainfall. Silent zero-substitution is forbidden.")
        if pre_storm_do_mg_L is None or np.isnan(pre_storm_do_mg_L):
            return self._build_refusal("Missing pre-storm dissolved oxygen measurement.")

        if pre_storm_water_temp_c < 0.0 or pre_storm_water_temp_c > 35.0:
            return self._build_refusal(f"Pre-storm water temperature ({pre_storm_water_temp_c:.1f}°C) is outside physical liquid stream bounds.")
        if storm_rain_mm < 0.0:
            return self._build_refusal(f"Negative rainfall ({storm_rain_mm:.1f} mm) is physically impossible.")

        # 2. Check if stream is already in violation at forecast issue time
        if pre_storm_do_mg_L <= thr:
            return {
                "status": "IMMEDIATE_BREACH",
                "is_supported": True,
                "message": f"Pre-storm DO ({pre_storm_do_mg_L:.2f} mg/L) is already at or below the risk threshold ({thr:.2f} mg/L).",
                "actionable_window_hours": 0.0,
                "earliest_crossing_hours": 0.0,
                "median_crossing_hours": 0.0,
                "latest_crossing_hours": 0.0,
                "crossing_probabilities_by_horizon": {f"{h}h": 1.0 for h in ACTION_WINDOW_HORIZONS},
                "confidence_assessment": "Definite observed breach at forecast issue time.",
                "disclaimer": SCIENTIFIC_SAFEGUARDS["action_window_disclaimer"],
            }

        # 3. Hydrodynamic Lag Modulation based on Schuylkill empirical catchment parameters
        # Base lag to hydrograph peak ~ 6-12 hours; longer rainfall duration prolongs runoff delivery
        duration_term = 0.30 * max(2.0, min(36.0, storm_duration_hours))
        rain_momentum_term = 0.15 * max(0.0, min(50.0, storm_rain_mm))

        # Temperature kinetic acceleration: warmer temperatures accelerate bacterial BOD exertion
        if pre_storm_water_temp_c >= 22.0:
            kinetic_shift = -3.5  # Earlier nadir in warm summer
        elif pre_storm_water_temp_c < 10.0:
            kinetic_shift = 4.0   # Muted, delayed deoxygenation in winter
        else:
            kinetic_shift = 0.0

        adj_nadir_median = float(np.clip(self.t_nadir_median + duration_term + kinetic_shift, 8.0, 56.0))
        adj_nadir_p10 = float(np.clip(self.t_nadir_p10 + 0.5 * duration_term + kinetic_shift, 4.0, 30.0))
        adj_nadir_p90 = float(np.clip(self.t_nadir_p90 + 1.2 * duration_term + kinetic_shift, 18.0, 68.0))

        # 4. Estimate Expected Minimum DO if not provided
        if expected_min_do_72h is None:
            # First-order urban washoff depletion approximation
            temp_factor = 1.0 + max(0.0, (pre_storm_water_temp_c - 15.0) / 10.0)
            rain_eff = max(0.0, storm_rain_mm)
            depletion = (1.0 - np.exp(-rain_eff / 25.0)) * 2.5 * temp_factor
            exp_min_do = max(1.5, pre_storm_do_mg_L - depletion)
        else:
            exp_min_do = float(expected_min_do_72h)

        # Total expected depletion
        total_depletion = max(0.05, pre_storm_do_mg_L - exp_min_do)
        breach_margin = pre_storm_do_mg_L - thr

        # 5. Threshold Crossing Latency Estimation
        # Crossing occurs before nadir when DO curve intersects threshold
        crossing_expected = (exp_min_do < thr)

        if crossing_expected:
            crossing_ratio = float(np.clip(breach_margin / total_depletion, 0.05, 0.95))
            t_cross_median = round(adj_nadir_median * crossing_ratio, 1)
            t_cross_earliest = round(max(2.0, adj_nadir_p10 * crossing_ratio), 1)
            t_cross_latest = round(min(72.0, adj_nadir_p90 * crossing_ratio), 1)
        else:
            # Nadir remains above threshold in central scenario
            # Plausible crossing only occurs in tail uncertainty
            t_cross_median = None  # No central crossing
            t_cross_earliest = round(adj_nadir_p10 * 0.85, 1) if (prob_72h_crossing or 0.0) > 0.15 else None
            t_cross_latest = None

        # 6. Cumulative Horizon Crossing Probabilities (6, 12, 24, 48, 72 hours)
        base_p72 = prob_72h_crossing if prob_72h_crossing is not None else (0.75 if crossing_expected else 0.08)
        horizon_probs = {}

        for h in ACTION_WINDOW_HORIZONS:
            if crossing_expected and t_cross_median is not None:
                if h < t_cross_earliest:
                    p_h = base_p72 * 0.05 * (h / max(1.0, t_cross_earliest))
                elif h < t_cross_median:
                    frac = (h - t_cross_earliest) / max(1.0, t_cross_median - t_cross_earliest)
                    p_h = base_p72 * (0.10 + 0.40 * frac)
                elif h < t_cross_latest:
                    frac = (h - t_cross_median) / max(1.0, t_cross_latest - t_cross_median)
                    p_h = base_p72 * (0.50 + 0.45 * frac)
                else:
                    p_h = base_p72
            else:
                # Low overall risk: scale smoothly up to 72h tail risk
                p_h = base_p72 * (h / 72.0) ** 1.8

            horizon_probs[f"{h}h"] = round(float(np.clip(p_h, 0.0, 1.0)), 4)

        # Operational action window: time remaining before earliest plausible breach
        if crossing_expected and t_cross_earliest is not None:
            effective_action_window = t_cross_earliest
        else:
            effective_action_window = adj_nadir_median

        return {
            "status": "VALID_ESTIMATE",
            "is_supported": True,
            "threshold_mg_L": thr,
            "pre_storm_do_mg_L": round(pre_storm_do_mg_L, 2),
            "expected_min_do_72h": round(exp_min_do, 2),
            "crossing_expected_in_central_scenario": crossing_expected,
            "estimated_action_window_hours": effective_action_window,
            "earliest_plausible_crossing_hours": t_cross_earliest,
            "median_estimated_crossing_hours": t_cross_median,
            "latest_plausible_crossing_hours": t_cross_latest,
            "estimated_time_to_nadir_hours": adj_nadir_median,
            "crossing_probabilities_by_horizon": horizon_probs,
            "methodology_notes": (
                "Timing bounds derived from empirical nadir distributions across 58 storm disturbance events "
                "at USGS 01474500. This is an estimated statistical action window, NOT a guaranteed countdown clock."
            ),
            "disclaimer": SCIENTIFIC_SAFEGUARDS["action_window_disclaimer"],
        }

    def _build_refusal(self, reason: str) -> Dict[str, Any]:
        """Constructs standardized refusal response when inputs are insufficient."""
        return {
            "status": "REFUSAL",
            "is_supported": False,
            "message": f"{SCIENTIFIC_SAFEGUARDS['refusal_prefix']} Reason: {reason}",
            "reasons": [reason],
            "actionable_window_hours": None,
            "earliest_crossing_hours": None,
            "median_crossing_hours": None,
            "latest_crossing_hours": None,
            "crossing_probabilities_by_horizon": {f"{h}h": None for h in ACTION_WINDOW_HORIZONS},
            "disclaimer": SCIENTIFIC_SAFEGUARDS["action_window_disclaimer"],
        }
