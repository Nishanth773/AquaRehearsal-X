"""
AquaRehearsal-X - Operational Time-Feasibility Filter
Stage 4: Risk-to-Action Decision Support

Evaluates whether a candidate intervention can physically be mobilized, deployed,
and exert an environmental effect before dissolved oxygen breaches a critical threshold.

Mandatory Scientific Principles:
1. Strict Temporal Feasibility: Compares total required lead time
   (preparation + implementation + environmental lag) against the estimated action window.
2. Anti-Ranking Rule: Interventions are NEVER automatically ranked by simulated magnitude,
   nor is a single 'winner' or 'recommended action' selected.
3. Transparent Logistics: All logistical bottlenecks (crew dispatch, SCADA drawdown,
   maturation timescales) are explicitly reported for side-by-side comparison.
"""

from typing import Dict, Any, List, Optional
import numpy as np

from src.config.stage4_settings import FEASIBILITY_TIERS, SCIENTIFIC_SAFEGUARDS
from src.rehearsal.intervention_parameters import (
    AerationConfig,
    RunoffReductionConfig,
    DetentionConfig,
    RiparianShadingConfig,
)


class FeasibilityFilter:
    """
    Evaluates logistical time feasibility of intervention scenarios against
    the estimated action window.
    """

    def __init__(self, feasibility_tiers: Optional[Dict[str, Dict[str, str]]] = None):
        self.tiers = feasibility_tiers or FEASIBILITY_TIERS

    def evaluate_feasibility(
        self,
        intervention_type: str,
        intervention_config: Any,
        action_window_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assesses whether the intervention can plausibly be completed in time.

        Args:
            intervention_type: 'temporary_aeration', 'runoff_reduction', 'stormwater_detention', 'riparian_shading'.
            intervention_config: Config object with timing attributes.
            action_window_data: Output dictionary from ActionWindowEstimator.

        Returns:
            Dictionary with feasibility tier, timing margins, and operational constraints.
        """
        # 1. Check for refusal / insufficient evidence in upstream action window
        if not action_window_data.get("is_supported", False):
            return self._build_tier_response(
                "INSUFFICIENT_EVIDENCE",
                lead_time=getattr(intervention_config, "total_deployment_lead_hours", 0.0),
                window_time=0.0,
                reason="Upstream action window could not be estimated due to missing or invalid sensor inputs.",
            )

        # 2. Extract Lead Time Components
        prep_time = float(getattr(intervention_config, "min_prep_time_hours", 4.0))
        impl_time = float(getattr(intervention_config, "implementation_time_hours", 1.0))
        lag_time = float(getattr(intervention_config, "effect_lag_hours", 1.0))
        total_lead = prep_time + impl_time + lag_time

        # 3. Extract Action Window Timings
        window_hours = action_window_data.get("estimated_action_window_hours")
        earliest_crossing = action_window_data.get("earliest_plausible_crossing_hours")
        median_crossing = action_window_data.get("median_estimated_crossing_hours")

        # Fallback to general window if crossing not anticipated in central run
        target_deadline = earliest_crossing if earliest_crossing is not None else (window_hours or 24.0)

        # 4. Long-Term Structural Interventions (e.g., Riparian Shading)
        if intervention_type == "riparian_shading" or total_lead > 72.0:
            return self._build_tier_response(
                "UNLIKELY_TO_AFFECT",
                lead_time=total_lead,
                prep_time=prep_time,
                impl_time=impl_time,
                lag_time=lag_time,
                window_time=target_deadline,
                reason=(
                    f"Riparian canopy establishment requires multi-year sapling maturation (~{prep_time / 8760:.0f} years). "
                    "It provides long-term watershed resilience but cannot physically mitigate an imminent storm event."
                ),
                operational_constraints=[
                    "Land acquisition / riparian easement agreements required.",
                    "Multi-year sapling growth and canopy closure period.",
                    "Zero acute responsiveness for incoming wet-weather pulse.",
                ],
            )

        # 5. Immediate breach check
        if action_window_data.get("status") == "IMMEDIATE_BREACH":
            return self._build_tier_response(
                "UNLIKELY_TO_AFFECT",
                lead_time=total_lead,
                prep_time=prep_time,
                impl_time=impl_time,
                lag_time=lag_time,
                window_time=0.0,
                reason=f"Stream DO is already in violation at forecast issue time. Required deployment time ({total_lead:.1f}h) exceeds available window.",
                operational_constraints=["Deployment cannot precede an event that has already occurred."],
            )

        # 6. Time Feasibility Comparison
        time_margin = target_deadline - total_lead

        if time_margin >= 0.0:
            tier_key = "POTENTIALLY_FEASIBLE"
            reason = (
                f"Total deployment lead time ({total_lead:.1f}h) is within the estimated action window ({target_deadline:.1f}h), "
                f"providing an estimated operational margin of {time_margin:.1f} hours before critical threshold crossing."
            )
        elif median_crossing is not None and total_lead <= (median_crossing + 2.0):
            tier_key = "FEASIBILITY_UNCERTAIN"
            reason = (
                f"Total lead time ({total_lead:.1f}h) exceeds earliest plausible crossing ({target_deadline:.1f}h) "
                f"but falls within median crossing timing ({median_crossing:.1f}h). Successful deployment requires rapid emergency mobilization."
            )
        else:
            tier_key = "UNLIKELY_TO_AFFECT"
            reason = (
                f"Total required lead time ({total_lead:.1f}h) exceeds the plausible action window ({target_deadline:.1f}h) "
                f"by {abs(time_margin):.1f} hours. The intervention is unlikely to exert an in-stream effect before the DO trough."
            )

        # Operational constraints specific to archetype
        constraints = self._get_archetype_constraints(intervention_type, intervention_config)

        return self._build_tier_response(
            tier_key,
            lead_time=total_lead,
            prep_time=prep_time,
            impl_time=impl_time,
            lag_time=lag_time,
            window_time=target_deadline,
            reason=reason,
            operational_constraints=constraints,
        )

    def _get_archetype_constraints(self, intervention_type: str, config: Any) -> List[str]:
        if intervention_type == "temporary_aeration":
            return [
                "Requires on-site electrical power or diesel generator refueling logistics.",
                "Navigational clearance permits required for surface-mounted aerators in commercial river channels.",
                "Limited spatial reach: effective primarily within 1-3 km of injection point.",
            ]
        elif intervention_type == "runoff_reduction":
            return [
                "Requires coordinated municipal dispatch for pre-storm street sweeping and inlet vacuuming.",
                "Effectiveness strongly dependent on whether rainfall exceeds local bioretention infiltration rates.",
                "Diminishing returns once catchment soils reach full saturation.",
            ]
        elif intervention_type == "stormwater_detention":
            return [
                "Requires functional SCADA telemetry and calibrated hydraulic gate controllers.",
                "Risk of basin overflow / untreated bypass if precipitation depth exceeds chamber capacity.",
                "Post-storm release must be coordinated with downstream receiving-water capacity to avoid secondary surge.",
            ]
        else:
            return ["Long-term watershed planning constraints."]

    def _build_tier_response(
        self,
        tier_key: str,
        lead_time: float,
        window_time: float,
        prep_time: float = 0.0,
        impl_time: float = 0.0,
        lag_time: float = 0.0,
        reason: str = "",
        operational_constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        tier_info = self.tiers[tier_key]
        return {
            "feasibility_tier": tier_key,
            "feasibility_label": tier_info["label"],
            "badge_color": tier_info["badge_color"],
            "total_deployment_lead_hours": round(lead_time, 1),
            "prep_time_hours": round(prep_time, 1),
            "implementation_time_hours": round(impl_time, 1),
            "effect_lag_hours": round(lag_time, 1),
            "target_deadline_hours": round(window_time, 1),
            "time_margin_hours": round(window_time - lead_time, 1),
            "assessment_summary": reason,
            "operational_constraints": operational_constraints or [],
            "disclaimer": SCIENTIFIC_SAFEGUARDS["ranking_rule"],
        }
