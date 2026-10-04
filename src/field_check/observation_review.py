"""
AquaRehearsal-X - Observation Review & Verification Workflow
Stage 5: Citizen Observation and Prediction Verification System

Manages the formal review workflow for authorized environmental scientists:
1. Transition states: PENDING_REVIEW -> VERIFIED, REJECTED, NEEDS_CONFIRMATION, INCOMPLETE, DUPLICATE.
2. Immutable audit trail of every status transition with reviewer ID, timestamp, and rationale.
3. Strict Verification Mandate: No observation is marked 'VERIFIED' without explicit human-in-the-loop review.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.field_check.field_observation_schema import FieldObservation, ReviewAuditEntry
from src.config.stage5_settings import REVIEW_STATES
from src.utils.logger import logger


class ObservationReviewWorkflow:
    """Manages the verification lifecycle and audit history of citizen reports."""

    def __init__(self, allowed_states: Optional[List[str]] = None):
        self.allowed_states = allowed_states or REVIEW_STATES

    def transition_status(
        self,
        observation: FieldObservation,
        new_status: str,
        reviewer_id: str,
        review_notes: str,
    ) -> FieldObservation:
        """
        Transitions the verification status of an observation and appends to the audit trail.
        """
        if new_status not in self.allowed_states:
            raise ValueError(f"Invalid verification status '{new_status}'. Allowed: {self.allowed_states}")

        prev_status = observation.verification_status
        now_utc = datetime.now(timezone.utc).isoformat() + "Z"

        audit_entry = ReviewAuditEntry(
            timestamp=now_utc,
            reviewer_id=reviewer_id,
            previous_state=prev_status,
            new_state=new_status,
            review_notes=review_notes.strip(),
        )

        observation.verification_status = new_status
        observation.review_audit_trail.append({
            "timestamp": audit_entry.timestamp,
            "reviewer_id": audit_entry.reviewer_id,
            "previous_state": audit_entry.previous_state,
            "new_state": audit_entry.new_state,
            "review_notes": audit_entry.review_notes,
        })

        logger.info(
            "Observation %s status transitioned from %s -> %s by reviewer %s",
            observation.observation_id, prev_status, new_status, reviewer_id
        )
        return observation

    def filter_by_status(
        self,
        observations: List[FieldObservation],
        status: str,
    ) -> List[FieldObservation]:
        """Filters a list of observations by verification status."""
        return [obs for obs in observations if obs.verification_status == status]
