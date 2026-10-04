"""
AquaRehearsal-X - Structured Logger
Provides clean, consistent logging for data engineering operations.
"""

import logging
import sys
from typing import Optional


def setup_logger(name: str = "AquaRehearsalX", level: int = logging.INFO) -> logging.Logger:
    """Configures and returns a standardized logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger()
