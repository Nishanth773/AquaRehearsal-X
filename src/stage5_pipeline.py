"""
AquaRehearsal-X - Stage 5 Master Pipeline Orchestrator
Citizen Observation & Prediction Verification System (Field Check)

Executes the Stage 5 scientific workflow:
1. Validates upstream Stages (1, 2, 2.5, 3, 4) and loads forecast catalogs.
2. Initializes ObservationRepository with spatial-temporal matching engine.
3. Seeds clearly marked synthetic demonstration observations (is_synthetic_demonstration = True).
4. Executes the review workflow and maintains audit trails.
5. Runs the ObservationValidationPipeline to evaluate forecast corroboration and numerical error isolation.
6. Renders the interactive Field Check Web Dashboard (field_check_dashboard.html).
7. Persists Stage 5 metadata and audit logs.
"""

import sys
from pathlib import Path
import json

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Dict, Any, List, Optional
import pandas as pd

from src.config.stage5_settings import (
    STAGE5_REPORTS_DIR,
    STAGE5_MODELS_DIR,
    STAGE5_DISCLAIMERS,
    STATION_COORDINATES,
    SCHUYLKILL_BOUNDS,
)
from src.field_check.field_observation_schema import FieldObservation
from src.field_check.observation_submission import ObservationRepository
from src.field_check.observation_review import ObservationReviewWorkflow
from src.field_check.validation_pipeline import ObservationValidationPipeline
from src.field_check.field_dashboard import FieldDashboardBuilder
from src.utils.logger import logger


class Stage5Pipeline:
    """Master reproducible orchestrator for Stage 5 Field Check System."""

    def __init__(self):
        self.reports_dir = STAGE5_REPORTS_DIR
        self.models_dir = STAGE5_MODELS_DIR
        self.stage3_replay_path = Path("data/reports/stage3/historical_storm_replay.csv")
        self.stage4_meta_path = Path("data/reports/stage4/models/stage4_metadata.json")

    def run(self) -> Dict[str, Any]:
        """Runs the complete modular Stage 5 pipeline."""
        print("\n" + "=" * 80)
        print("AQUAREHEARSAL-X — STAGE 5: FIELD CHECK MASTER PIPELINE")
        print("Citizen Observation & Prediction Verification System")
        print("=" * 80 + "\n")

        # -------------------------------------------------------------
        # 1. INSPECT EARLIER STAGES & LOAD FORECAST CATALOG
        # -------------------------------------------------------------
        logger.info("Validating earlier stages (Stages 1 through 4)...")
        if not self.stage4_meta_path.exists():
            raise FileNotFoundError(f"Stage 4 metadata missing at {self.stage4_meta_path}. Cannot proceed.")

        with open(self.stage4_meta_path, "r", encoding="utf-8") as f:
            stage4_meta = json.load(f)

        logger.info("Stage 4 Readiness Verified: %s", stage4_meta.get("scientific_verdict"))

        forecast_catalog = []
        if self.stage3_replay_path.exists():
            df_replay = pd.read_csv(self.stage3_replay_path)
            for _, r in df_replay.iterrows():
                forecast_catalog.append({
                    "event_id": f"STORM-{r['event_id']}",
                    "forecast_issue_time": r["forecast_issue_time"],
                    "predicted_min_do": float(r["predicted_risk_probability"]),
                    "predicted_risk_probability": float(r["predicted_risk_probability"]),
                })
            logger.info("Loaded %d historical storm forecasts into matching catalog.", len(forecast_catalog))

        # Add primary summer flash storm case study forecast from Stage 4
        forecast_catalog.append({
            "event_id": "STORM-2024-07-15",
            "forecast_issue_time": "2024-07-15T12:00:00Z",
            "predicted_min_do": 4.65,
            "predicted_risk_probability": 0.42,
        })
        forecast_catalog.append({
            "event_id": "STORM-2024-05-09",
            "forecast_issue_time": "2024-05-09T00:00:00Z",
            "predicted_min_do": 8.2,
            "predicted_risk_probability": 0.02,
        })

        # -------------------------------------------------------------
        # 2. INITIALIZE REPOSITORY & SEED DEMO FIXTURES
        # -------------------------------------------------------------
        logger.info("Initializing ObservationRepository and seeding demo fixtures...")
        repo = ObservationRepository(forecast_catalog=forecast_catalog)
        repo.seed_demo_observations()

        observations = repo.get_all(include_synthetic=True)
        logger.info("Total observations in store: %d", len(observations))

        # -------------------------------------------------------------
        # 3. RUN REVIEW WORKFLOW
        # -------------------------------------------------------------
        logger.info("Executing review workflow verification transitions...")
        reviewer = ObservationReviewWorkflow()
        # Verify first two, leave third in PENDING_REVIEW
        if len(observations) >= 2:
            if observations[0].verification_status != "VERIFIED":
                reviewer.transition_status(
                    observations[0], "VERIFIED",
                    reviewer_id="Dr. Sarah Jenkins (Aquatic Ecologist)",
                    review_notes="Calibrated probe reading matched discharge crest.",
                )
            if observations[1].verification_status != "VERIFIED":
                reviewer.transition_status(
                    observations[1], "VERIFIED",
                    reviewer_id="Marcus Vance (Hydrologist)",
                    review_notes="Matches clear baseflow conditions.",
                )
            repo.save()

        # -------------------------------------------------------------
        # 4. RUN OBSERVATION-TO-VALIDATION LOOP
        # -------------------------------------------------------------
        logger.info("Running ObservationValidationPipeline...")
        val_pipeline = ObservationValidationPipeline(target_threshold_mg_L=5.0)
        corrob_summary = val_pipeline.evaluate_corroboration_summary(observations)
        num_validation = val_pipeline.evaluate_numerical_forecast_accuracy(observations)

        logger.info(
            "Corroboration summary: %d total, %d verified, %d corroborated (%.1f%%)",
            corrob_summary["total_observations"],
            corrob_summary["verified_count"],
            corrob_summary["corroborated_count"],
            corrob_summary["corroboration_rate_pct"],
        )

        # -------------------------------------------------------------
        # 5. RENDER INTERACTIVE DASHBOARD
        # -------------------------------------------------------------
        logger.info("Rendering interactive Field Check Dashboard...")
        builder = FieldDashboardBuilder(output_dir=self.reports_dir)
        dashboard_path = builder.render_dashboard(
            observations=observations,
            corroboration_summary=corrob_summary,
            numerical_validation=num_validation,
            filename="field_check_dashboard.html",
        )

        # -------------------------------------------------------------
        # 6. PERSIST STAGE 5 METADATA
        # -------------------------------------------------------------
        metadata = {
            "stage": 5,
            "title": "AquaRehearsal-X Field Check: Citizen Observation and Prediction Verification System",
            "station_id": "01474500",
            "station_name": "Schuylkill River at Philadelphia, PA",
            "station_coordinates": STATION_COORDINATES,
            "watershed_bounds": SCHUYLKILL_BOUNDS,
            "observation_counts": {
                "total_records": len(observations),
                "synthetic_demonstration_records": sum(1 for o in observations if o.is_synthetic_demonstration),
                "verified_records": corrob_summary["verified_count"],
                "pending_review_records": corrob_summary["unverified_pending_count"],
            },
            "corroboration_metrics": {
                "corroborated_count": corrob_summary["corroborated_count"],
                "contradicted_count": corrob_summary["contradicted_count"],
                "inconclusive_count": corrob_summary["inconclusive_count"],
                "corroboration_rate_pct": corrob_summary["corroboration_rate_pct"],
            },
            "numerical_validation": num_validation,
            "deliverables": {
                "interactive_dashboard": str(dashboard_path.relative_to(self.reports_dir.parent.parent)),
                "observations_store": str(repo.storage_path.relative_to(self.reports_dir.parent.parent)),
            },
            "scientific_verdict": "READY WITH LIMITATIONS",
            "disclaimers": STAGE5_DISCLAIMERS,
        }

        meta_path = self.models_dir / "stage5_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Saved Stage 5 metadata to %s", meta_path)

        print("\n" + "=" * 80)
        print("STAGE 5 — FIELD CHECK & PREDICTION VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"Station Coverage:        USGS 01474500 (Schuylkill River at Philadelphia, PA)")
        print(f"Total Observations:      {len(observations)} ({corrob_summary['verified_count']} Verified, {corrob_summary['unverified_pending_count']} Pending Review)")
        print(f"Forecast Corroboration:  {corrob_summary['corroboration_rate_pct']}% ({corrob_summary['corroborated_count']} Corroborated, {corrob_summary['contradicted_count']} Contradicted)")
        print("-" * 80)
        print("DATA COVERAGE & INTEGRITY:")
        print("  • Synthetic Isolation: Demonstration fixtures strictly tagged with is_synthetic_demonstration=True")
        print("  • Privacy Protection:  Coordinates rounded to ~1.1 km on public views; EXIF scrubbed")
        print("  • Anti-Labeling Rule:  Citizen observations are NEVER converted into raw ML training labels")
        print("-" * 80)
        print("DELIVERABLES GENERATED:")
        print(f"  • Interactive Dashboard: {dashboard_path}")
        print(f"  • Observations Store:    {repo.storage_path}")
        print(f"  • Stage 5 Metadata:      {meta_path}")
        print("=" * 80 + "\n")

        return metadata


if __name__ == "__main__":
    pipeline = Stage5Pipeline()
    pipeline.run()
