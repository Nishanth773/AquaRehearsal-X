"""
AquaRehearsal-X - Storm Tolerance Envelope (STE) Engine
Stage 3: Dynamic Resilience Boundaries & Multi-Dimensional Conditioning

Defines the multi-dimensional tolerance space in which incoming hydrologic and meteorological
disturbances can be absorbed by the stream without crossing critical dissolved oxygen
ecological and regulatory thresholds (PA DEP 5.0 mg/L, 4.0 mg/L, and acute hypoxia 2.0 mg/L).

Mathematical Foundation:
- Dynamic assimilative capacity is governed by temperature-dependent oxygen solubility DO_sat(T),
  ambient baseline DO, antecedent catchment saturation (API_72h), and discharge surge ratio (Q_peak / Q_base).
- For an ambient state S = (T, Q_base, DO_base, API_72h), the Critical Rainfall Depth R_crit(tau)
  and Critical Discharge Surge Q_crit(tau) delineate the boundary:
      E[DO_min^72h | S, R_crit, Q_crit] = tau
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from src.config.stage3_settings import (
    STAGE3_REGULATORY_THRESHOLDS,
    THERMAL_TIERS,
    ANTECEDENT_MOISTURE_TIERS,
    STAGE2_5_MODELS_DIR,
)
from src.features.storm_features import StormFeatureBuilder
from src.utils.logger import logger


def calculate_benson_krause_saturation(temp_c: float) -> float:
    """
    Computes theoretical dissolved oxygen saturation (mg/L) at 1 atm pressure
    using the standard Benson & Krause (1984) / USGS formula.
    """
    t_k = temp_c + 273.15
    if t_k <= 0:
        return 14.6
    ln_do_sat = (
        -139.34411
        + (1.575701e5 / t_k)
        - (6.642308e7 / (t_k**2))
        + (1.243800e10 / (t_k**3))
        - (8.621949e11 / (t_k**4))
    )
    return float(np.clip(np.exp(ln_do_sat), 4.0, 15.0))


class StormToleranceEnvelope:
    """
    Computes dynamic resilience boundaries, critical thresholds, and buffer margins
    conditioned on antecedent hydrologic and thermal states.
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        regulatory_thresholds: Optional[Dict[str, float]] = None,
    ):
        self.thresholds = regulatory_thresholds or STAGE3_REGULATORY_THRESHOLDS
        self.model_path = Path(model_path or (STAGE2_5_MODELS_DIR / "model_water_plus_precipitation.joblib"))
        self.ml_model = None
        self._load_ml_model()

    def _load_ml_model(self):
        """Loads trained Model B artifact if available."""
        if self.model_path.exists():
            try:
                self.ml_model = joblib.load(self.model_path)
                logger.info("StormToleranceEnvelope loaded Model B from %s", self.model_path)
            except Exception as e:
                logger.warning("Could not load ML model from %s: %s. Using analytical STE fallback.", self.model_path, e)
                self.ml_model = None
        else:
            logger.info("Model path %s not found. Using calibrated analytical STE formulation.", self.model_path)

    @staticmethod
    def get_thermal_tier(temp_c: float) -> str:
        """Categorizes ambient water temperature into cold, moderate, or warm regimes."""
        if temp_c < 15.0:
            return "cold"
        elif temp_c < 22.0:
            return "moderate"
        else:
            return "warm"

    @staticmethod
    def get_antecedent_moisture_tier(api_72h_mm: float) -> str:
        """Categorizes 72-hour antecedent rainfall into dry, normal, or saturated regimes."""
        if api_72h_mm < 5.0:
            return "dry"
        elif api_72h_mm < 20.0:
            return "normal"
        else:
            return "wet"

    def estimate_minimum_do(
        self,
        ambient_temp_c: float,
        ambient_do_mg_L: float,
        ambient_discharge_cfs: float,
        storm_rain_mm: float,
        discharge_surge_ratio: float,
        antecedent_rain_72h_mm: float = 0.0,
    ) -> float:
        """
        Estimates expected minimum dissolved oxygen over the next 72 hours
        given pre-storm ambient state and incoming storm magnitude.
        
        Uses an empirical response surface calibrated to the Schuylkill River 2023-2026 dataset:
        - DO_saturation sets the thermodynamic upper ceiling.
        - Higher temperature increases microbial deoxygenation kinetics (Q10 ~ 2.0).
        - Higher rainfall and discharge surge wash in BOD and sediment, driving DO down.
        - Saturated antecedent soils accelerate runoff and exacerbate DO depression.
        """
        do_sat = calculate_benson_krause_saturation(ambient_temp_c)
        base_do = min(ambient_do_mg_L, do_sat * 1.05)
        
        # Temperature stress factor: normalized relative to 15°C reference
        # As temperature rises towards 28°C, biological deoxygenation doubles
        temp_stress_factor = 1.0 + max(0.0, (ambient_temp_c - 15.0) / 10.0) * 1.15
        
        # Antecedent moisture modifier: saturated catchments yield faster/larger runoff wash-off
        moisture_tier = self.get_antecedent_moisture_tier(antecedent_rain_72h_mm)
        runoff_mult = ANTECEDENT_MOISTURE_TIERS[moisture_tier]["runoff_modifier"]
        
        # Effective rainfall disturbance input (in mm)
        effective_rain = max(0.0, storm_rain_mm) * runoff_mult
        
        # Surge impact: logarithmic response to discharge increase ratio
        surge_ratio = max(1.0, discharge_surge_ratio)
        surge_impact = np.log1p(surge_ratio - 1.0) * 0.45
        
        # Rainfall impact: saturating non-linear depletion
        # Small storms (<10mm) produce modest depletion; large storms (>40mm) trigger significant BOD/CSO flush
        rain_impact = (1.0 - np.exp(-effective_rain / 28.0)) * 2.85
        
        total_depletion = (rain_impact + surge_impact) * temp_stress_factor
        
        # Minimum physical DO floor (anoxic lower bound ~ 0.5 mg/L)
        expected_min_do = max(0.5, base_do - total_depletion)
        return float(expected_min_do)

    def compute_critical_rainfall(
        self,
        ambient_temp_c: float,
        ambient_do_mg_L: float,
        ambient_discharge_cfs: float,
        discharge_surge_ratio: float = 3.0,
        antecedent_rain_72h_mm: float = 0.0,
        target_threshold: float = 4.0,
    ) -> float:
        """
        Finds the Critical Rainfall Depth R_crit (mm) beyond which minimum DO is expected
        to fall below target_threshold (e.g. 4.0 mg/L acute standard).
        
        Returns 0.0 if the stream is already below threshold,
        or 150.0+ if the stream can absorb extreme rainfall without crossing.
        """
        # Binary search for R_crit
        low, high = 0.0, 150.0
        
        # Check boundary at low
        do_at_zero = self.estimate_minimum_do(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            storm_rain_mm=0.0,
            discharge_surge_ratio=discharge_surge_ratio,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
        )
        if do_at_zero <= target_threshold:
            return 0.0
            
        do_at_max = self.estimate_minimum_do(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            storm_rain_mm=high,
            discharge_surge_ratio=discharge_surge_ratio,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
        )
        if do_at_max > target_threshold:
            return high  # Stream has ample capacity; even 150mm won't breach
            
        for _ in range(30):
            mid = (low + high) / 2.0
            val = self.estimate_minimum_do(
                ambient_temp_c=ambient_temp_c,
                ambient_do_mg_L=ambient_do_mg_L,
                ambient_discharge_cfs=ambient_discharge_cfs,
                storm_rain_mm=mid,
                discharge_surge_ratio=discharge_surge_ratio,
                antecedent_rain_72h_mm=antecedent_rain_72h_mm,
            )
            if val < target_threshold:
                high = mid
            else:
                low = mid
        return float(np.round((low + high) / 2.0, 1))

    def compute_critical_discharge(
        self,
        ambient_temp_c: float,
        ambient_do_mg_L: float,
        ambient_discharge_cfs: float,
        storm_rain_mm: float = 15.0,
        antecedent_rain_72h_mm: float = 0.0,
        target_threshold: float = 4.0,
    ) -> float:
        """
        Finds the Critical Discharge Surge Ratio Q_crit beyond which minimum DO
        is expected to fall below target_threshold.
        """
        low, high = 1.0, 25.0
        do_at_1 = self.estimate_minimum_do(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            storm_rain_mm=storm_rain_mm,
            discharge_surge_ratio=1.0,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
        )
        if do_at_1 <= target_threshold:
            return 1.0
            
        do_at_25 = self.estimate_minimum_do(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            storm_rain_mm=storm_rain_mm,
            discharge_surge_ratio=high,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
        )
        if do_at_25 > target_threshold:
            return high
            
        for _ in range(30):
            mid = (low + high) / 2.0
            val = self.estimate_minimum_do(
                ambient_temp_c=ambient_temp_c,
                ambient_do_mg_L=ambient_do_mg_L,
                ambient_discharge_cfs=ambient_discharge_cfs,
                storm_rain_mm=storm_rain_mm,
                discharge_surge_ratio=mid,
                antecedent_rain_72h_mm=antecedent_rain_72h_mm,
            )
            if val < target_threshold:
                high = mid
            else:
                low = mid
        return float(np.round((low + high) / 2.0, 2))

    def evaluate_envelope(
        self,
        ambient_temp_c: float,
        ambient_do_mg_L: float,
        ambient_discharge_cfs: float,
        incoming_rain_mm: float,
        incoming_discharge_surge_ratio: float,
        antecedent_rain_72h_mm: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Comprehensive evaluation of the Storm Tolerance Envelope for a given storm scenario.
        Returns expected minimum DO, critical boundaries, buffer margins, and risk classification.
        """
        expected_min_do = self.estimate_minimum_do(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            storm_rain_mm=incoming_rain_mm,
            discharge_surge_ratio=incoming_discharge_surge_ratio,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
        )

        # Critical boundaries
        r_crit_standard = self.compute_critical_rainfall(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            discharge_surge_ratio=incoming_discharge_surge_ratio,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
            target_threshold=self.thresholds["standard_protection"],
        )
        r_crit_acute = self.compute_critical_rainfall(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            discharge_surge_ratio=incoming_discharge_surge_ratio,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
            target_threshold=self.thresholds["acute_stress"],
        )
        r_crit_hypoxia = self.compute_critical_rainfall(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            discharge_surge_ratio=incoming_discharge_surge_ratio,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
            target_threshold=self.thresholds["severe_hypoxia"],
        )

        q_crit_acute = self.compute_critical_discharge(
            ambient_temp_c=ambient_temp_c,
            ambient_do_mg_L=ambient_do_mg_L,
            ambient_discharge_cfs=ambient_discharge_cfs,
            storm_rain_mm=incoming_rain_mm,
            antecedent_rain_72h_mm=antecedent_rain_72h_mm,
            target_threshold=self.thresholds["acute_stress"],
        )

        # Buffer margins (positive = safe buffer; negative = breached standard)
        buffer_standard = expected_min_do - self.thresholds["standard_protection"]
        buffer_acute = expected_min_do - self.thresholds["acute_stress"]
        buffer_hypoxia = expected_min_do - self.thresholds["severe_hypoxia"]

        # Remaining assimilative capacity percentage relative to 4.0 mg/L
        do_sat = calculate_benson_krause_saturation(ambient_temp_c)
        max_possible_buffer = max(0.1, do_sat - self.thresholds["acute_stress"])
        current_buffer = max(0.0, expected_min_do - self.thresholds["acute_stress"])
        remaining_capacity_pct = float(np.clip((current_buffer / max_possible_buffer) * 100.0, 0.0, 100.0))

        # Risk Zone Classification
        if expected_min_do >= self.thresholds["standard_protection"]:
            risk_zone = "SAFE / FULL TOLERANCE"
            zone_code = "SAFE"
        elif expected_min_do >= self.thresholds["acute_stress"]:
            risk_zone = "ADVISORY / BUFFER EROSION"
            zone_code = "ADVISORY"
        elif expected_min_do >= self.thresholds["severe_hypoxia"]:
            risk_zone = "WARNING / ENVELOPE BREACHED"
            zone_code = "WARNING"
        else:
            risk_zone = "EMERGENCY / ACUTE HYPOXIA HAZARD"
            zone_code = "EMERGENCY"

        thermal_tier = self.get_thermal_tier(ambient_temp_c)
        moisture_tier = self.get_antecedent_moisture_tier(antecedent_rain_72h_mm)

        return {
            "expected_minimum_do_mg_L": round(expected_min_do, 2),
            "risk_zone": risk_zone,
            "zone_code": zone_code,
            "thermal_tier": thermal_tier,
            "antecedent_moisture_tier": moisture_tier,
            "saturation_do_mg_L": round(do_sat, 2),
            "buffer_standard_5_0_mg_L": round(buffer_standard, 2),
            "buffer_acute_4_0_mg_L": round(buffer_acute, 2),
            "buffer_hypoxia_2_0_mg_L": round(buffer_hypoxia, 2),
            "remaining_assimilative_capacity_pct": round(remaining_capacity_pct, 1),
            "critical_rainfall_standard_5_0_mm": r_crit_standard,
            "critical_rainfall_acute_4_0_mm": r_crit_acute,
            "critical_rainfall_hypoxia_2_0_mm": r_crit_hypoxia,
            "critical_discharge_surge_ratio_4_0": q_crit_acute,
            "incoming_storm_rain_mm": incoming_rain_mm,
            "incoming_discharge_surge_ratio": incoming_discharge_surge_ratio,
        }

    def generate_2d_envelope_grid(
        self,
        ambient_temp_c: float,
        ambient_do_mg_L: float,
        ambient_discharge_cfs: float,
        antecedent_rain_72h_mm: float = 0.0,
        rain_steps: int = 60,
        surge_steps: int = 60,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates a 2D meshgrid of storm rainfall [0, 80 mm] vs. discharge surge ratio [1x, 15x]
        and evaluates expected minimum DO across the grid.
        Useful for generating 2D phase space contour maps of tolerance boundaries.
        """
        rain_grid = np.linspace(0.0, 80.0, rain_steps)
        surge_grid = np.linspace(1.0, 15.0, surge_steps)
        R_mesh, S_mesh = np.meshgrid(rain_grid, surge_grid)
        
        DO_mesh = np.zeros_like(R_mesh)
        for i in range(surge_steps):
            for j in range(rain_steps):
                DO_mesh[i, j] = self.estimate_minimum_do(
                    ambient_temp_c=ambient_temp_c,
                    ambient_do_mg_L=ambient_do_mg_L,
                    ambient_discharge_cfs=ambient_discharge_cfs,
                    storm_rain_mm=R_mesh[i, j],
                    discharge_surge_ratio=S_mesh[i, j],
                    antecedent_rain_72h_mm=antecedent_rain_72h_mm,
                )
        return R_mesh, S_mesh, DO_mesh
