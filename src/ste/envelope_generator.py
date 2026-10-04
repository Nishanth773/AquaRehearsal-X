"""
AquaRehearsal-X - Storm Tolerance Envelope (STE) Generator
Component: envelope_generator.py

Generates the 2D Rainfall-versus-Water-Temperature Storm Tolerance Envelope:
- Evaluates estimated probability P(DO_min^72h < tau) over a fine 2D meshgrid:
    X-axis: Cumulative storm rainfall (mm)
    Y-axis: Pre-storm water temperature (°C)
- Delineates the Storm Tolerance Envelope as the contour line where estimated risk reaches
  the configurable operational risk limit (default 20% / P = 0.20).
- Segregates the state space into:
    * SAFE REGION: P(DO_min < tau) < risk_limit
    * ELEVATED-RISK REGION: P(DO_min < tau) >= risk_limit
- Enforces empirical domain masking: unsupported combinations outside the observed historical
  convex hull are masked to prevent unwarranted statistical extrapolation.
- Preserves natural non-linear response without forcing artificial mathematical monotonicity.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import numpy as np
import pandas as pd

from src.ste.risk_model import EcologicalRiskModel
from src.ste.domain_support_checker import DomainSupportChecker
from src.utils.logger import logger


class StormToleranceEnvelopeGenerator:
    """
    Constructs the 2D Rainfall-vs-Temperature risk surface, operational envelope boundary,
    and empirical support mask.
    """

    def __init__(
        self,
        risk_model: Optional[EcologicalRiskModel] = None,
        domain_checker: Optional[DomainSupportChecker] = None,
        operational_risk_limit: float = 0.20,
        default_threshold_mg_L: float = 5.0,
    ):
        self.risk_model = risk_model or EcologicalRiskModel(default_threshold_mg_L=default_threshold_mg_L)
        self.domain_checker = domain_checker or DomainSupportChecker()
        self.risk_limit = operational_risk_limit
        self.threshold = default_threshold_mg_L

    def set_parameters(
        self,
        threshold_mg_L: Optional[float] = None,
        operational_risk_limit: Optional[float] = None,
    ):
        """Updates active ecological threshold and operational risk limit."""
        if threshold_mg_L is not None:
            self.threshold = float(threshold_mg_L)
            self.risk_model.set_threshold(self.threshold)
        if operational_risk_limit is not None:
            if operational_risk_limit <= 0.0 or operational_risk_limit >= 1.0:
                raise ValueError("Operational risk limit must be strictly between 0.0 and 1.0 (e.g. 0.20).")
            self.risk_limit = float(operational_risk_limit)

    def generate_surface_grid(
        self,
        rain_range_mm: Tuple[float, float] = (0.0, 70.0),
        temp_range_c: Tuple[float, float] = (1.0, 31.0),
        rain_steps: int = 71,
        temp_steps: int = 61,
        pre_storm_do_mg_L: Optional[float] = None,
        pre_storm_discharge_cfs: Optional[float] = None,
        antecedent_rain_72h_mm: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Evaluates the 2D response surface and extracts the safe boundary contour.
        """
        rain_vec = np.linspace(rain_range_mm[0], rain_range_mm[1], rain_steps)
        temp_vec = np.linspace(temp_range_c[0], temp_range_c[1], temp_steps)
        
        # R_mesh: shape (temp_steps, rain_steps); X-axis is Rainfall, Y-axis is Temperature
        R_mesh, T_mesh = np.meshgrid(rain_vec, temp_vec)
        prob_surface = np.zeros_like(R_mesh)

        for i in range(temp_steps):
            for j in range(rain_steps):
                prob_surface[i, j] = self.risk_model.estimate_risk_probability(
                    storm_rain_mm=R_mesh[i, j],
                    pre_storm_water_temp_c=T_mesh[i, j],
                    pre_storm_do_mg_L=pre_storm_do_mg_L,
                    pre_storm_discharge_cfs=pre_storm_discharge_cfs,
                    antecedent_rain_72h_mm=antecedent_rain_72h_mm,
                    threshold_mg_L=self.threshold,
                )

        # Generate domain support mask
        support_mask = self.domain_checker.create_support_mask_2d(R_mesh, T_mesh)

        # Safe region is where risk is below limit AND inside supported domain
        safe_mask = (prob_surface < self.risk_limit) & support_mask
        elevated_risk_mask = (prob_surface >= self.risk_limit) & support_mask
        unsupported_mask = ~support_mask

        # Extract 1D boundary curve: critical rainfall R_crit(T) where P = risk_limit
        boundary_temps = []
        boundary_r_crit = []

        for i in range(temp_steps):
            t_val = temp_vec[i]
            probs_at_t = prob_surface[i, :]
            # Check if risk contour is crossed along the rain vector
            cross_indices = np.where(np.diff(probs_at_t >= self.risk_limit))[0]
            if len(cross_indices) > 0:
                idx = cross_indices[0]
                # Linear interpolation between adjacent grid cells
                r0, r1 = rain_vec[idx], rain_vec[idx + 1]
                p0, p1 = probs_at_t[idx], probs_at_t[idx + 1]
                if abs(p1 - p0) > 1e-6:
                    r_interp = r0 + (self.risk_limit - p0) * (r1 - r0) / (p1 - p0)
                else:
                    r_interp = r0
                boundary_temps.append(float(t_val))
                boundary_r_crit.append(float(np.clip(r_interp, 0.0, rain_range_mm[1])))
            else:
                if probs_at_t[0] >= self.risk_limit:
                    boundary_temps.append(float(t_val))
                    boundary_r_crit.append(0.0)  # Stream exceeds risk even at zero rain
                elif probs_at_t[-1] < self.risk_limit:
                    boundary_temps.append(float(t_val))
                    boundary_r_crit.append(float(rain_range_mm[1]))

        return {
            "rainfall_vector_mm": rain_vec.tolist(),
            "temperature_vector_c": temp_vec.tolist(),
            "R_mesh": R_mesh,
            "T_mesh": T_mesh,
            "probability_surface": prob_surface,
            "support_mask": support_mask,
            "safe_mask": safe_mask,
            "elevated_risk_mask": elevated_risk_mask,
            "unsupported_mask": unsupported_mask,
            "operational_risk_limit": self.risk_limit,
            "do_threshold_mg_L": self.threshold,
            "boundary_curve": {
                "temperature_c": boundary_temps,
                "critical_rainfall_mm": boundary_r_crit,
            },
        }
