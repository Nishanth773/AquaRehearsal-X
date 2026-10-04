"""
AquaRehearsal-X - Transparent Oxygen-Balance Scenario Model
Stage 4: Risk-to-Action Decision Support

Provides an interpretable, physically grounded dissolved oxygen (DO) mass-balance solver
to simulate hourly stream DO trajectories across a 72-hour storm disturbance window.

Governing Equations (Streeter-Phelps with Storm Washoff & Aeration Flux):
    dC/dt = K_a(T) * (C_s(T) - C(t)) - K_d(T) * L(t) - SOD(T) + R_aeration(t)
    dL/dt = -K_r(T) * L(t) + W_storm(t)

Where:
    C(t)       = Dissolved oxygen concentration (mg/L)
    C_s(T)     = Benson-Krause (1984) temperature-dependent DO saturation (mg/L)
    K_a(T)     = Surface reaeration rate (1/h), Arrhenius temperature corrected (theta = 1.024)
    K_d(T)     = CBOD deoxygenation rate (1/h), temperature corrected (theta = 1.047)
    K_r(T)     = Total CBOD removal rate (deoxygenation + settling) (1/h)
    SOD(T)     = Sediment oxygen demand rate (mg/L/h), temperature corrected (theta = 1.065)
    W_storm(t) = Storm-driven organic washoff loading pulse (mg BOD/L/h)
    R_aeration = Direct mechanical/diffused oxygen transfer flux (mg DO/L/h)

Scientific Safeguards:
- Explicit separation between measured inputs (T, DO_0, Q, Rain) and assumed kinetics (K_a, K_d, SOD).
- Results are explicitly documented as exploratory simulations, NOT measured real-world treatment effects.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from src.ste.envelope_engine import calculate_benson_krause_saturation
from src.rehearsal.intervention_parameters import (
    AerationConfig,
    RunoffReductionConfig,
    DetentionConfig,
    RiparianShadingConfig,
)
from src.config.stage4_settings import SCIENTIFIC_SAFEGUARDS
from src.utils.logger import logger


class OxygenBalanceModel:
    """
    Simulates hourly stream dissolved oxygen dynamics under baseline conditions
    and hypothetical intervention scenarios.
    """

    def __init__(
        self,
        ka_20_per_hour: float = 0.038,       # ~0.91 / day at 20°C (O'Connor-Dobbins Schuylkill calibration)
        kd_20_per_hour: float = 0.012,       # ~0.29 / day at 20°C
        kr_20_per_hour: float = 0.018,       # ~0.43 / day at 20°C
        sod_20_mg_L_h: float = 0.022,        # ~1.3 g O2 / m² / day divided by depth ~2.5m
        channel_depth_m: float = 2.5,
    ):
        self.ka_20 = ka_20_per_hour
        self.kd_20 = kd_20_per_hour
        self.kr_20 = kr_20_per_hour
        self.sod_20 = sod_20_mg_L_h
        self.depth_m = channel_depth_m

    def simulate_trajectory(
        self,
        pre_storm_water_temp_c: float,
        pre_storm_do_mg_L: float,
        pre_storm_discharge_cfs: float,
        storm_rain_mm: float,
        storm_duration_hours: float = 18.0,
        intervention_type: Optional[str] = None,
        intervention_config: Optional[Any] = None,
        simulation_hours: int = 72,
        dt_hours: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Solves the continuous mass balance across the 72-hour window.

        Args:
            pre_storm_water_temp_c: Baseline water temperature (°C).
            pre_storm_do_mg_L: Initial pre-storm DO (mg/L).
            pre_storm_discharge_cfs: Base streamflow (cfs).
            storm_rain_mm: Cumulative storm precipitation (mm).
            storm_duration_hours: Rainfall event duration (hours).
            intervention_type: None for baseline, or 'aeration', 'runoff', 'detention', 'shading'.
            intervention_config: Dataclass instance with intervention parameters.
            simulation_hours: Forward simulation horizon (default 72h).
            dt_hours: Integration step (default 0.25h for numerical stability).

        Returns:
            Dictionary with hourly DO trajectory, minimum DO, nadir time, and kinetics audit.
        """
        # Validate inputs
        if pre_storm_water_temp_c is None or np.isnan(pre_storm_water_temp_c):
            raise ValueError("Pre-storm water temperature cannot be NaN.")
        if storm_rain_mm is None or np.isnan(storm_rain_mm):
            raise ValueError("Storm rainfall cannot be NaN.")
        if pre_storm_do_mg_L is None or np.isnan(pre_storm_do_mg_L):
            raise ValueError("Pre-storm DO cannot be NaN.")

        # 1. Temperature & Kinetics Adjustments (including riparian shading if active)
        active_temp = float(pre_storm_water_temp_c)
        if intervention_type == "riparian_shading" and isinstance(intervention_config, RiparianShadingConfig):
            active_temp = max(1.0, active_temp - intervention_config.stream_temperature_reduction_c)

        # Benson-Krause theoretical saturation
        cs = calculate_benson_krause_saturation(active_temp)

        # Temperature-corrected rate coefficients
        ka = self.ka_20 * (1.024 ** (active_temp - 20.0))
        kd = self.kd_20 * (1.047 ** (active_temp - 20.0))
        kr = self.kr_20 * (1.047 ** (active_temp - 20.0))
        sod = self.sod_20 * (1.065 ** (active_temp - 20.0))

        # Velocity and depth scaling with discharge
        q_ratio = max(0.5, pre_storm_discharge_cfs / 1200.0)
        ka *= (q_ratio ** 0.15)  # Turbulence reaeration enhancement

        # 2. Storm Organic Washoff Pulse W_storm(t)
        # Washoff load magnitude scales with rainfall and antecedent washoff capacity
        effective_rain = max(0.0, storm_rain_mm)
        bod_reduction_mult = 1.0

        if intervention_type == "runoff_reduction" and isinstance(intervention_config, RunoffReductionConfig):
            # Reduced surface washoff volume & particulate load
            treated_frac = intervention_config.treated_catchment_fraction
            vol_red = intervention_config.runoff_volume_reduction_pct / 100.0
            effective_rain *= (1.0 - treated_frac * vol_red)
            bod_reduction_mult = 1.0 - (intervention_config.bod_load_reduction_pct / 100.0) * treated_frac

        # Peak wash-off timing and detention attenuation
        peak_time = max(4.0, storm_duration_hours * 0.55)
        pulse_width = max(3.0, storm_duration_hours * 0.40)

        if intervention_type == "stormwater_detention" and isinstance(intervention_config, DetentionConfig):
            # Check for basin capacity exceedance / overflow bypass
            if storm_rain_mm > intervention_config.overflow_threshold_rain_mm:
                # Partial attenuation until overflow
                bypass_fraction = (storm_rain_mm - intervention_config.overflow_threshold_rain_mm) / storm_rain_mm
                eff_attenuation = (intervention_config.peak_attenuation_pct / 100.0) * (1.0 - bypass_fraction)
            else:
                eff_attenuation = intervention_config.peak_attenuation_pct / 100.0

            bod_reduction_mult *= (1.0 - 0.5 * eff_attenuation)
            peak_time += intervention_config.controlled_release_delay_hours * 0.45  # Hydrograph delay
            pulse_width *= (1.0 + eff_attenuation * 1.5)  # Hydrograph attenuation / flattening

        total_bod_load = (1.0 - np.exp(-effective_rain / 22.0)) * 14.5 * bod_reduction_mult

        # 3. Numerical Integration (Euler with sub-hourly step)
        n_steps = int(simulation_hours / dt_hours)
        time_steps = np.linspace(0, simulation_hours, n_steps + 1)

        c = float(min(pre_storm_do_mg_L, cs))  # Initial DO
        l = float(3.2)                         # Baseline ambient stream CBOD (mg/L)

        traj_times = []
        traj_do = []
        traj_bod = []

        for step in range(n_steps + 1):
            t_curr = time_steps[step]

            # Washoff delivery rate at current time (Gamma-shaped pulse)
            if effective_rain > 0.5:
                shape_val = max(0.0, (t_curr - 2.0) / pulse_width)
                w_t = (total_bod_load / pulse_width) * shape_val * np.exp(-shape_val)
            else:
                w_t = 0.0

            # Active aeration flux
            r_aeration = 0.0
            if intervention_type == "temporary_aeration" and isinstance(intervention_config, AerationConfig):
                start_h = intervention_config.start_delay_hours
                end_h = start_h + intervention_config.duration_hours
                if start_h <= t_curr <= end_h:
                    r_aeration = intervention_config.oxygen_transfer_rate_mg_L_h

            # Hourly checkpoint recording
            if step % int(1.0 / dt_hours) == 0:
                traj_times.append(round(float(t_curr), 1))
                traj_do.append(round(float(c), 3))
                traj_bod.append(round(float(l), 3))

            # Derivatives
            dc_dt = ka * (cs - c) - kd * l - sod + r_aeration
            dl_dt = -kr * l + w_t

            # Forward update
            c = float(np.clip(c + dc_dt * dt_hours, 0.5, cs * 1.05))
            l = float(max(0.5, l + dl_dt * dt_hours))

        arr_do = np.array(traj_do)
        min_do = float(np.min(arr_do))
        nadir_idx = int(np.argmin(arr_do))
        nadir_time = float(traj_times[nadir_idx])

        return {
            "intervention_type": intervention_type or "baseline",
            "active_water_temperature_c": round(active_temp, 2),
            "saturation_do_mg_L": round(cs, 2),
            "minimum_do_mg_L": round(min_do, 2),
            "time_to_nadir_hours": nadir_time,
            "total_depletion_mg_L": round(float(pre_storm_do_mg_L - min_do), 2),
            "hourly_timestamps_hours": traj_times,
            "hourly_do_trajectory_mg_L": traj_do,
            "hourly_cbod_trajectory_mg_L": traj_bod,
            "kinetics_parameters": {
                "ka_per_hour": round(ka, 4),
                "kd_per_hour": round(kd, 4),
                "kr_per_hour": round(kr, 4),
                "sod_mg_L_h": round(sod, 4),
            },
            "disclaimer": SCIENTIFIC_SAFEGUARDS["causal_disclaimer"],
        }

    def compute_sensitivity_bounds(
        self,
        pre_storm_water_temp_c: float,
        pre_storm_do_mg_L: float,
        pre_storm_discharge_cfs: float,
        storm_rain_mm: float,
        intervention_type: Optional[str] = None,
        intervention_config: Optional[Any] = None,
        parameter_variation_pct: float = 25.0,
    ) -> Dict[str, Any]:
        """
        Runs sensitivity analysis by perturbing rate coefficients Ka, Kd, and SOD by +/- 25%.
        """
        # Central run
        base_res = self.simulate_trajectory(
            pre_storm_water_temp_c, pre_storm_do_mg_L, pre_storm_discharge_cfs, storm_rain_mm,
            intervention_type=intervention_type, intervention_config=intervention_config
        )

        orig_ka = self.ka_20
        orig_kd = self.kd_20
        orig_sod = self.sod_20

        # Optimistic (high reaeration, lower decomposition)
        frac = parameter_variation_pct / 100.0
        self.ka_20 = orig_ka * (1.0 + frac)
        self.kd_20 = orig_kd * (1.0 - frac)
        self.sod_20 = orig_sod * (1.0 - frac)
        opt_res = self.simulate_trajectory(
            pre_storm_water_temp_c, pre_storm_do_mg_L, pre_storm_discharge_cfs, storm_rain_mm,
            intervention_type=intervention_type, intervention_config=intervention_config
        )

        # Pessimistic (sluggish reaeration, intense decomposition)
        self.ka_20 = orig_ka * (1.0 - frac)
        self.kd_20 = orig_kd * (1.0 + frac)
        self.sod_20 = orig_sod * (1.0 + frac)
        pess_res = self.simulate_trajectory(
            pre_storm_water_temp_c, pre_storm_do_mg_L, pre_storm_discharge_cfs, storm_rain_mm,
            intervention_type=intervention_type, intervention_config=intervention_config
        )

        # Restore
        self.ka_20 = orig_ka
        self.kd_20 = orig_kd
        self.sod_20 = orig_sod

        return {
            "central": base_res,
            "optimistic_trajectory": opt_res["hourly_do_trajectory_mg_L"],
            "pessimistic_trajectory": pess_res["hourly_do_trajectory_mg_L"],
            "min_do_range": [pess_res["minimum_do_mg_L"], opt_res["minimum_do_mg_L"]],
            "parameter_variation_pct": parameter_variation_pct,
        }
