"""
AquaRehearsal-X - Stage 3: Storm Tolerance Envelope (STE) Modular Package
Components:
- storm_event_detector: Identifies physical storm disturbance events and resolves overlapping windows
- domain_support_checker: Enforces data boundaries and transparent refusal logic
- risk_model: Formulates probabilistic risk surfaces for configurable DO thresholds
- risk_calibration: Evaluates Brier scores, reliability diagrams, and discrimination metrics
- envelope_generator: Generates 2D Rainfall-vs-Temperature safe boundaries
- boundary_uncertainty: Quantifies envelope confidence bands via event-level block bootstrap
- historical_storm_replay: Replays held-out storms and records lead times to threshold crossing
- envelope_visualization: Generates 2D publication figures and interactive HTML platform
"""

from src.ste.storm_event_detector import StormEventDetector
from src.ste.domain_support_checker import DomainSupportChecker
from src.ste.risk_model import EcologicalRiskModel
from src.ste.risk_calibration import RiskCalibrator
from src.ste.envelope_generator import StormToleranceEnvelopeGenerator
from src.ste.boundary_uncertainty import BoundaryUncertaintyEstimator
from src.ste.historical_storm_replay import HistoricalStormReplay
from src.ste.envelope_visualization import EnvelopeVisualizer

# Backward-compatibility exports
from src.ste.envelope_engine import StormToleranceEnvelope, calculate_benson_krause_saturation
from src.ste.probability_engine import StratifiedUncertaintyCalibrator, BoundaryCrossingProbability
from src.ste.action_window import ActionWindowEstimator
from src.ste.event_evaluator import HistoricalSTEEvaluator

__all__ = [
    "StormEventDetector",
    "DomainSupportChecker",
    "EcologicalRiskModel",
    "RiskCalibrator",
    "StormToleranceEnvelopeGenerator",
    "BoundaryUncertaintyEstimator",
    "HistoricalStormReplay",
    "EnvelopeVisualizer",
    "StormToleranceEnvelope",
    "calculate_benson_krause_saturation",
    "StratifiedUncertaintyCalibrator",
    "BoundaryCrossingProbability",
    "ActionWindowEstimator",
    "HistoricalSTEEvaluator",
]
