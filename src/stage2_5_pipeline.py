"""
AquaRehearsal-X - Stage 2.5 Master Pipeline Orchestrator
Historical Depth + Real Precipitation Upgrade

Executes the complete Stage 2.5 scientific workflow:
1. Data Coverage Comparison Audit (Stage 2 vs Stage 2.5)
2. Multi-Year Historical Storm Event Detection & Precipitation Enrichment
3. Model A (Water-Only) vs Model B (Water + Precipitation) Training & Validation
4. Uncertainty Quantification & Interval Reliability Evaluation
5. Storm-Specific and Normal Period Evaluation
6. 10 Publication-Grade Scientific Visualizations
7. Model Artifact & Metadata Persistence
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.stage2_5_settings import (
    STAGE2_5_DATA_CONFIG,
    STAGE2_5_REPORTS_DIR,
    STAGE2_5_PLOTS_DIR,
    PROCESSED_DATA_DIR,
)
from src.analysis.stage2_5_audit import DataCoverageAuditor
from src.analysis.historical_storm_events import HistoricalStormEnricher
from src.models.stage2_5_models import Stage2_5ModelComparison
from src.models.stage2_5_plotting import Stage2_5Plotter
from src.utils.logger import logger


class Stage2_5Pipeline:
    """Master orchestrator for Stage 2.5."""

    def __init__(self):
        self.data_path = PROCESSED_DATA_DIR / STAGE2_5_DATA_CONFIG["extended_data_file"]
        self.reports_dir = STAGE2_5_REPORTS_DIR
        self.plotter = Stage2_5Plotter(output_dir=STAGE2_5_PLOTS_DIR)

    def run(self):
        """Runs the complete Stage 2.5 end-to-end pipeline."""
        logger.info("=" * 70)
        logger.info("AQUAREHEARSAL-X — STAGE 2.5: HISTORICAL DEPTH + REAL PRECIPITATION")
        logger.info("=" * 70)

        # 1. Data Coverage Audit
        auditor = DataCoverageAuditor()
        df_coverage = auditor.generate_audit_report()
        print("\n" + "=" * 70)
        print("DATA COVERAGE COMPARISON: STAGE 2 (CURRENT) vs STAGE 2.5 (EXTENDED)")
        print("=" * 70)
        print(df_coverage.to_string(index=False))
        print("=" * 70 + "\n")

        # 2. Detect & Enrich Historical Storm Events
        enricher = HistoricalStormEnricher()
        df_events = enricher.detect_and_enrich_events()

        # 3. Model A vs Model B Training and Comparison
        comparison = Stage2_5ModelComparison(data_path=self.data_path)
        comp_results = comparison.run_comparison()

        df_comp = comp_results["comparison_df"]
        df_storm_backtest = comp_results["storm_backtest_df"]
        df_imp_b = comp_results["feature_importance_b"]
        df_test = comp_results["df_test"]
        y_test_pred_a = comp_results["y_test_pred_a"]
        y_test_pred_b = comp_results["y_test_pred_b"]
        q10_b = comp_results["q10_b"]
        q90_b = comp_results["q90_b"]

        print("\n" + "=" * 90)
        print("STAGE 2.5 MODEL COMPARISON (MODEL A: WATER-ONLY vs MODEL B: WATER + PRECIPITATION)")
        print("=" * 90)
        print(df_comp.to_string(index=False))
        print("=" * 90 + "\n")

        # 4. Generate 10 Scientific Visualizations
        logger.info("Generating 10 publication-grade scientific visualizations...")
        df_all = pd.read_csv(self.data_path)
        df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], utc=True)
        df_all = df_all.set_index("timestamp").sort_index()

        self.plotter.plot_1_longterm_do_timeline(df_all)
        self.plotter.plot_2_longterm_rainfall_timeline(df_all)
        self.plotter.plot_3_rainfall_vs_discharge(df_all)
        self.plotter.plot_4_rainfall_vs_do_response(df_all)
        self.plotter.plot_5_storm_event_rainfall_hydrographs(df_all, df_events)
        self.plotter.plot_6_actual_vs_predicted_min_do(
            df_test["target_min_do_72h"].to_numpy(),
            y_test_pred_a,
            y_test_pred_b,
        )
        self.plotter.plot_7_model_a_vs_model_b_comparison(df_comp)
        self.plotter.plot_8_storm_event_error_comparison(df_storm_backtest)
        self.plotter.plot_9_rainfall_feature_importance(df_imp_b)
        self.plotter.plot_10_prediction_interval_behavior(
            df_test.index,
            df_test["target_min_do_72h"].to_numpy(),
            y_test_pred_b,
            q10_b,
            q90_b,
        )

        logger.info("Stage 2.5 Pipeline Completed Successfully.")


if __name__ == "__main__":
    import pandas as pd
    pipeline = Stage2_5Pipeline()
    pipeline.run()
