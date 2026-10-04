"""
AquaRehearsal-X - Scenario Comparison & Trade-Off Matrix
Stage 4: Risk-to-Action Decision Support

Builds transparent side-by-side comparison matrices across all four intervention archetypes.
Adheres strictly to the Anti-Ranking Rule: no single 'winner' is declared; each action is
evaluated alongside its logistical constraints and environmental trade-offs.
"""

from typing import Dict, Any, List
import pandas as pd

from src.config.stage4_settings import SCIENTIFIC_SAFEGUARDS


class ScenarioComparison:
    """Formats scenario rehearsal results into transparent comparison tables and matrices."""

    @staticmethod
    def build_comparison_dataframe(rehearsal_result: Dict[str, Any]) -> pd.DataFrame:
        """
        Converts multi-scenario rehearsal dictionary into a structured comparison DataFrame.
        """
        if rehearsal_result.get("status") != "SUCCESS":
            return pd.DataFrame()

        base_min_do = rehearsal_result["baseline"]["simulated_minimum_do_mg_L"]
        base_risk = rehearsal_result["baseline"]["estimated_risk_probability"]

        rows = []

        # Add Baseline row
        rows.append({
            "Intervention": "Baseline (No Action)",
            "Category": "Status Quo",
            "Total Lead Time (h)": 0.0,
            "Target Deadline (h)": rehearsal_result["action_window"].get("estimated_action_window_hours", 0.0),
            "Time Margin (h)": 0.0,
            "Feasibility Tier": "BASELINE",
            "Simulated Min DO (mg/L)": base_min_do,
            "DO Gain (mg/L)": 0.0,
            "Projected Risk P(DO<5.0)": base_risk,
            "Primary Constraint": "Unmitigated storm washoff & deoxygenation",
        })

        for itype, data in rehearsal_result["rehearsal_scenarios"].items():
            feas = data["feasibility"]
            sim = data["simulation"]
            env = data["envelope_mapping"]

            display_name = {
                "temporary_aeration": "Temporary In-Stream Aeration",
                "runoff_reduction": "Catchment Runoff Reduction",
                "stormwater_detention": "Stormwater & CSO Detention",
                "riparian_shading": "Riparian Buffer Canopy Shading",
            }.get(itype, itype)

            category = {
                "temporary_aeration": "Active Mechanical",
                "runoff_reduction": "Catchment Source Control",
                "stormwater_detention": "Dynamic Hydraulic Storage",
                "riparian_shading": "Long-Term Structural",
            }.get(itype, "Ecological")

            proj_risk = env["scenario"]["estimated_risk_probability"] if (env.get("is_supported") and "scenario" in env) else base_risk
            first_constraint = feas["operational_constraints"][0] if feas["operational_constraints"] else "None specified"

            rows.append({
                "Intervention": display_name,
                "Category": category,
                "Total Lead Time (h)": feas["total_deployment_lead_hours"],
                "Target Deadline (h)": feas["target_deadline_hours"],
                "Time Margin (h)": feas["time_margin_hours"],
                "Feasibility Tier": feas["feasibility_tier"],
                "Simulated Min DO (mg/L)": sim["minimum_do_mg_L"],
                "DO Gain (mg/L)": sim["dissolved_oxygen_gain_mg_L"],
                "Projected Risk P(DO<5.0)": proj_risk,
                "Primary Constraint": first_constraint,
            })

        df = pd.DataFrame(rows)
        return df

    @staticmethod
    def get_anti_ranking_notice() -> str:
        return SCIENTIFIC_SAFEGUARDS["ranking_rule"]
