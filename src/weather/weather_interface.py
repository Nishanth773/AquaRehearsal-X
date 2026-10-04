"""
AquaRehearsal-X - Weather & Precipitation Interface Architecture
Stage 1: Real Data Foundation

Defines the interface specifications for weather, rainfall, and meteorological data
sources to be integrated in Stage 2.

Scientific Integrity:
- Does NOT fabricate rainfall values or mock API responses.
- Explicitly reports external weather services as not yet connected.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import pandas as pd

from src.utils.logger import logger


class WeatherDataSource(ABC):
    """Abstract interface specification for meteorological data providers."""

    @abstractmethod
    def fetch_historical_precipitation(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Retrieves real historical precipitation observations (e.g., NOAA NCEI, MRMS, ERA5).
        Returns DataFrame indexed by UTC timestamp with 'precipitation_mm' column,
        or None if not implemented / unavailable.
        """
        pass

    @abstractmethod
    def fetch_forecast_precipitation(
        self,
        latitude: float,
        longitude: float,
        forecast_horizon_hours: int = 72,
    ) -> Optional[pd.DataFrame]:
        """
        Retrieves real meteorological precipitation forecasts (e.g., NOAA HRRR, GFS).
        Returns DataFrame indexed by forecast UTC timestamp with 'forecast_precip_mm',
        or None if not implemented / unavailable.
        """
        pass


class NOAAWeatherPlaceholder(WeatherDataSource):
    """
    Placeholder client for NOAA High-Resolution Rapid Refresh (HRRR) and NCEI APIs.
    Stage 1 interface placeholder only. No values are fabricated.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def fetch_historical_precipitation(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        logger.warning(
            "NOAA historical precipitation integration is an interface placeholder in Stage 1. "
            "No synthetic or mock precipitation values will be generated."
        )
        return None

    def fetch_forecast_precipitation(
        self,
        latitude: float,
        longitude: float,
        forecast_horizon_hours: int = 72,
    ) -> Optional[pd.DataFrame]:
        logger.warning(
            "NOAA precipitation forecast integration is scheduled for Stage 2. "
            "No forecast values are fabricated."
        )
        return None

    def get_status(self) -> Dict[str, Any]:
        """Returns the readiness status of the weather integration."""
        return {
            "service": "NOAA Weather & MRMS Precipitation Interface",
            "stage_1_status": "INTERFACE_DEFINED",
            "data_connected": False,
            "scheduled_stage": "Stage 2",
            "notes": "Pending integration with NOAA CDO / HRRR / Open-Meteo public endpoints.",
        }
