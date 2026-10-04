"""
AquaRehearsal-X - Data Cleaning and Validation Module
Stage 1: Real Data Foundation

Implements rigorous, audited cleaning operations on raw sensor time series:
- Timezone normalization (UTC)
- Duplicate detection and resolution
- Physical boundary / invalid value checking
- Missing data accounting
- Transformation audit logging (never silently drops observations)
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config.settings import USGS_PARAM_CODES
from src.utils.logger import logger


class DataCleaningAudit:
    """Tracks every modification, exclusion, and anomaly detected during data cleaning."""

    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def record(self, action: str, variable: str, details: Dict[str, Any]):
        entry = {
            "action": action,
            "variable": variable,
            **details,
        }
        self.logs.append(entry)
        logger.info("Cleaning Audit: [%s] on %s: %s", action, variable, details)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.logs:
            return pd.DataFrame(columns=["action", "variable"])
        return pd.DataFrame(self.logs)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_actions": len(self.logs),
            "actions_breakdown": {
                log["action"]: sum(1 for x in self.logs if x["action"] == log["action"])
                for log in self.logs
            },
        }


class DataCleaner:
    """Scientific time-series data cleaner with transparent audit trail."""

    def __init__(self):
        self.audit = DataCleaningAudit()

    def clean_timeseries(
        self,
        df: pd.DataFrame,
        station_id: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, DataCleaningAudit]:
        """
        Cleans and standardizes raw observation DataFrame.

        Steps:
        1. Ensure DatetimeIndex with UTC timezone
        2. Sort chronologically
        3. Identify and handle duplicate timestamps
        4. Detect physical out-of-bounds observations and flag them
        5. Generate detailed audit log
        """
        if df.empty:
            logger.warning("Attempted to clean empty DataFrame.")
            return df.copy(), self.audit

        cleaned = df.copy()

        # Step 1: Ensure UTC DatetimeIndex
        if not isinstance(cleaned.index, pd.DatetimeIndex):
            self.audit.record(
                action="INDEX_CONVERSION",
                variable="timestamp",
                details={"reason": "Index was not DatetimeIndex, converting to UTC DatetimeIndex"},
            )
            cleaned.index = pd.to_datetime(cleaned.index, utc=True)
        elif cleaned.index.tz is None:
            self.audit.record(
                action="TIMEZONE_LOCALIZATION",
                variable="timestamp",
                details={"reason": "Index had no timezone, localizing to UTC"},
            )
            cleaned.index = cleaned.index.tz_localize("UTC")
        else:
            cleaned.index = cleaned.index.tz_convert("UTC")

        # Step 2: Sort chronologically
        if not cleaned.index.is_monotonic_increasing:
            self.audit.record(
                action="CHRONOLOGICAL_SORT",
                variable="timestamp",
                details={"reason": "Timestamps were not monotonic increasing"},
            )
            cleaned = cleaned.sort_index()

        # Step 3: Duplicate detection
        duplicate_mask = cleaned.index.duplicated(keep="last")
        dup_count = int(duplicate_mask.sum())
        if dup_count > 0:
            self.audit.record(
                action="DUPLICATES_RESOLVED",
                variable="timestamp",
                details={
                    "duplicate_count": dup_count,
                    "resolution": "Retained last observation per duplicate timestamp",
                    "duplicate_timestamps": [str(ts) for ts in cleaned.index[duplicate_mask][:10]],
                },
            )
            cleaned = cleaned[~duplicate_mask]

        # Step 4: Physical bounds and invalid value validation
        # Map known parameter columns to physical valid bounds
        for code, meta in USGS_PARAM_CODES.items():
            name = meta["name"]
            # Handle turbidity naming variations
            cols_to_check = [c for c in cleaned.columns if c == name or (name.startswith("turbidity") and c == "turbidity")]
            for col in cols_to_check:
                min_val = meta["min_valid"]
                max_val = meta["max_valid"]

                # Check lower bound
                below_bound = cleaned[col] < min_val
                below_count = int(below_bound.sum())
                if below_count > 0:
                    self.audit.record(
                        action="PHYSICAL_BOUND_VIOLATION_LOW",
                        variable=col,
                        details={
                            "count": below_count,
                            "threshold": min_val,
                            "unit": meta["unit"],
                            "action_taken": "flagged_and_set_to_nan",
                        },
                    )
                    cleaned[f"{col}_invalid_flag"] = below_bound
                    cleaned.loc[below_bound, col] = np.nan

                # Check upper bound
                above_bound = cleaned[col] > max_val
                above_count = int(above_bound.sum())
                if above_count > 0:
                    self.audit.record(
                        action="PHYSICAL_BOUND_VIOLATION_HIGH",
                        variable=col,
                        details={
                            "count": above_count,
                            "threshold": max_val,
                            "unit": meta["unit"],
                            "action_taken": "flagged_and_set_to_nan",
                        },
                    )
                    cleaned[f"{col}_invalid_flag"] = above_bound | cleaned.get(f"{col}_invalid_flag", False)
                    cleaned.loc[above_bound, col] = np.nan

        return cleaned, self.audit
