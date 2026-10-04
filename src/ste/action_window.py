"""
AquaRehearsal-X - Action Window & Time-to-Trough Estimator
Stage 3: Quantifying Response Latency and Operational Intervention Windows

Answers the critical resilience question:
"How much time remains to act before severe dissolved oxygen depletion occurs?"

Mathematical and Physical Foundation:
- Time-to-Trough (t_trough): The latency (in hours) between the initial disturbance trigger /
  storm onset (t_0) and the moment of maximum dissolved oxygen depletion (t_nadir).
- Operational Action Window (W_action): The effective temporal window [t_alert, t_nadir]
  during which pre-emptive interventions (weir adjustments, retention basin drawdown,
  CSO gate throttling, artificial aeration) can be physically deployed.
- Empirical dynamics at USGS 01474500 (Schuylkill River at Philadelphia):
  Watershed travel time (1,893 sq mi basin) induces a hydrologic lag of 6-18 hours to peak flow,
  followed by peak organic decomposition / BOD loading producing the DO nadir typically
  7 to 24+ hours after storm onset.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np
import pandas as pd

from src.config.stage3_settings import ACTION_WINDOW_TIERS
from src.utils.logger import logger


class ActionWindowEstimator:
    """
    Estimates the Time-to-Trough (hours) and characterizes the available
    operational action window for resilience interventions.
    """

    def __init__(self, action_tiers: Optional[Dict[str, Dict[str, Any]]] = None):
        self.tiers = action_tiers or ACTION_WINDOW_TIERS

    def estimate_time_to_trough(
        self,
        storm_duration_hours: float,
        discharge_surge_ratio: float,
        water_temperature_c: float,
        storm_rainfall_mm: float = 15.0,
    ) -> float:
        """
        Predicts expected hours from disturbance trigger to minimum DO trough.
        
        Calibrated to the empirical lag dynamics of Station 01474500:
        - Base travel time from mid-basin to Philadelphia gage ~ 6.0 hours.
        - Longer rainfall duration extends the runoff delivery window.
        - Higher discharge surge increases momentum and channel velocity slightly,
          but expands total wash-off volume.
        - Warmer water accelerates microbial kinetics, shifting the peak oxygen debt earlier.
        """
        # Baseline hydrodynamic lag (hours)
        base_lag = 6.0
        
        # Duration contribution (fraction of storm rainfall duration)
        duration_term = 0.35 * max(2.0, min(48.0, storm_duration_hours))
        
        # Surge volume contribution (larger surges prolong downstream hydrograph recession)
        surge_term = 0.85 * np.log1p(max(1.0, discharge_surge_ratio))
        
        # Temperature modulation: warm temperatures (~24°C) accelerate microbial BOD exertion
        # whereas cold temperatures delay peak deoxygenation
        if water_temperature_c >= 22.0:
            temp_term = -1.5  # Faster kinetics in summer
        elif water_temperature_c < 10.0:
            temp_term = 2.5   # Delayed, muted kinetics in winter
        else:
            temp_term = 0.0

        estimated_hours = base_lag + duration_term + surge_term + temp_term
        
        # Physical bounds: minimum lag ~ 4 hours (flashiest urban runoff); maximum within 72h window
        bounded_hours = float(np.clip(estimated_hours, 4.0, 48.0))
        return round(bounded_hours, 1)

    def characterize_action_window(
        self,
        estimated_time_to_trough: float,
        alert_latency_hours: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculates actionable time remaining after alert delivery and assigns operational urgency.
        """
        effective_window = max(0.5, estimated_time_to_trough - alert_latency_hours)
        
        if effective_window < 12.0:
            tier_key = "IMMEDIATE"
        elif effective_window <= 24.0:
            tier_key = "STANDARD"
        else:
            tier_key = "EXTENDED"

        tier_info = self.tiers[tier_key]
        
        return {
            "estimated_time_to_trough_hours": estimated_time_to_trough,
            "alert_latency_hours": alert_latency_hours,
            "actionable_window_hours": round(effective_window, 1),
            "urgency_tier": tier_key,
            "urgency_label": tier_info["label"],
            "recommended_operational_action": tier_info["recommended_action"],
        }
