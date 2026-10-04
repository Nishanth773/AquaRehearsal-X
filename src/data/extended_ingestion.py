"""
AquaRehearsal-X - Stage 2.5 Extended Ingestion Pipeline
Historical Depth + Real Precipitation Upgrade

Retrieves multi-year historical observations (2023-2026) for USGS 01474500
and merges with authoritative hourly precipitation from Open-Meteo Historical Weather API.
Strict Scientific Integrity:
- Never fabricates data.
- Preserves existing Stage 1 & Stage 2 raw files.
- Stores extended raw data in data/raw/extended/ with complete provenance.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import requests

from src.config.settings import (
    BASE_DIR,
    DATA_DIR,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    USGS_IV_URL,
)
from src.data.cleaner import DataCleaner
from src.data.resampler import DataResampler
from src.utils.logger import logger

EXTENDED_RAW_DIR = RAW_DATA_DIR / "extended"
EXTENDED_RAW_DIR.mkdir(parents=True, exist_ok=True)


class ExtendedDataIngestor:
    """Ingests multi-year USGS sensor records and authoritative gridded precipitation."""

    SITE_ID = "01474500"
    LATITUDE = 39.96779
    LONGITUDE = -75.18850
    USGS_PARAMS = ["00300", "00010", "00060", "63680", "00065"]

    DEFAULT_HEADERS = {
        "User-Agent": "AquaRehearsal-X/2.5 (IEEE Hackathon 2026; academic research; contact@aquarehearsal.org)",
        "Accept": "application/json, text/plain, */*",
    }

    def __init__(self, raw_dir: Path = EXTENDED_RAW_DIR, processed_dir: Path = PROCESSED_DATA_DIR):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def fetch_usgs_year(self, year: int, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetches a single calendar year of instantaneous values from USGS NWIS API."""
        cache_path = self.raw_dir / f"usgs_{self.SITE_ID}_{year}.json"
        if cache_path.exists() and not force_refresh:
            logger.info("Loading cached USGS data for year %d from %s", year, cache_path)
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        start_dt = f"{year}-01-01"
        end_dt = f"{year}-12-31" if year < 2026 else "2026-09-28"

        params = {
            "format": "json",
            "sites": self.SITE_ID,
            "parameterCd": ",".join(self.USGS_PARAMS),
            "startDT": start_dt,
            "endDT": end_dt,
            "siteStatus": "all",
        }

        logger.info("Querying USGS IV API for site %s for year %d (%s to %s)...", self.SITE_ID, year, start_dt, end_dt)
        resp = requests.get(USGS_IV_URL, params=params, headers=self.DEFAULT_HEADERS, timeout=60)
        resp.raise_for_status()
        raw_data = resp.json()

        packaged = {
            "provenance": {
                "source": "USGS Water Services - Instantaneous Values (IV) API",
                "station_id": self.SITE_ID,
                "year": year,
                "start_date": start_dt,
                "end_date": end_dt,
                "parameter_codes": self.USGS_PARAMS,
                "retrieval_date_utc": datetime.now(timezone.utc).isoformat(),
                "endpoint_url": resp.url,
            },
            "data": raw_data,
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(packaged, f, indent=2)
        logger.info("Saved raw USGS data for year %d to %s", year, cache_path)
        return packaged

    def fetch_openmeteo_precipitation(
        self,
        start_date: str = "2023-01-01",
        end_date: str = "2026-09-28",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieves real historical hourly rain (liquid precipitation) and precipitation from
        Open-Meteo Historical Weather API using explicitly selected ECMWF ERA5 reanalysis model.
        """
        cache_path = self.raw_dir / "precip_openmeteo_2023_2026.json"
        if cache_path.exists() and not force_refresh:
            logger.info("Loading cached Open-Meteo precipitation from %s", cache_path)
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": self.LATITUDE,
            "longitude": self.LONGITUDE,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "precipitation,rain",
            "models": "era5",
            "timezone": "UTC",
        }

        logger.info(
            "Querying Open-Meteo Historical Weather API (explicit model: era5) for coordinates (%.4f, %.4f) from %s to %s...",
            self.LATITUDE,
            self.LONGITUDE,
            start_date,
            end_date,
        )
        resp = requests.get(url, params=params, headers=self.DEFAULT_HEADERS, timeout=60)
        resp.raise_for_status()
        raw_data = resp.json()

        packaged = {
            "provenance": {
                "source": "Open-Meteo Historical Weather API",
                "exact_model_dataset": "ECMWF ERA5 Reanalysis (era5)",
                "requested_coordinates": {
                    "latitude": self.LATITUDE,
                    "longitude": self.LONGITUDE,
                },
                "returned_grid_coordinates": {
                    "latitude": raw_data.get("latitude"),
                    "longitude": raw_data.get("longitude"),
                    "elevation_m": raw_data.get("elevation"),
                },
                "spatial_resolution": "0.25 degree (~25-30 km grid cell)",
                "temporal_resolution": "1h (hourly)",
                "variables": {
                    "rain_mm": "rain (liquid precipitation, mm)",
                    "precipitation_mm": "precipitation (total liquid + solid water equivalent, mm)",
                },
                "primary_storm_variable": "rain_mm",
                "units": "millimeters (mm)",
                "retrieval_date_utc": datetime.now(timezone.utc).isoformat(),
                "start_date": start_date,
                "end_date": end_date,
                "endpoint_url": resp.url,
                "missing_value_convention": "Missing precipitation/rain = NaN; observed dry hour = 0.0 mm. Never convert missing to zero.",
                "geographic_scope_note": (
                    "Precipitation and rain data represent ECMWF ERA5 gridded reanalysis estimates "
                    "for the grid cell (Lat 40.0° N, Lon -75.25° W) containing the station coordinates "
                    "(Lat 39.9678, Lon -75.1885) and are NOT equivalent to watershed-average rainfall "
                    "across the 1,893 sq mi Schuylkill River catchment."
                ),
            },
            "data": raw_data,
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(packaged, f, indent=2)
        logger.info("Saved raw Open-Meteo precipitation to %s", cache_path)
        return packaged

    def parse_usgs_time_series(self, raw_json: Dict[str, Any]) -> pd.DataFrame:
        """Parses USGS NWIS JSON into structured DataFrame."""
        records = []
        data_block = raw_json.get("data", raw_json)
        time_series_list = data_block.get("value", {}).get("timeSeries", [])

        code_to_col = {
            "00300": "dissolved_oxygen",
            "00010": "water_temperature",
            "00060": "discharge",
            "00065": "gage_height",
            "63680": "turbidity",
            "00076": "turbidity",
        }

        series_by_param: Dict[str, pd.Series] = {}

        for ts in time_series_list:
            var_info = ts.get("variable", {})
            var_code = var_info.get("variableCode", [{}])[0].get("value")
            col_name = code_to_col.get(var_code)
            if not col_name:
                continue

            values_list = ts.get("values", [{}])[0].get("value", [])
            if not values_list:
                continue

            ts_dates = []
            ts_vals = []
            for item in values_list:
                dt_str = item.get("dateTime")
                val_str = item.get("value")
                if dt_str and val_str is not None:
                    try:
                        v = float(val_str)
                        if v != -999999.0:  # USGS null value indicator
                            ts_dates.append(dt_str)
                            ts_vals.append(v)
                    except ValueError:
                        continue

            if ts_dates:
                dt_index = pd.to_datetime(ts_dates, utc=True)
                s = pd.Series(ts_vals, index=dt_index, name=col_name)
                # Deduplicate index
                s = s[~s.index.duplicated(keep="first")]
                # If parameter already seen, combine/update
                if col_name in series_by_param:
                    series_by_param[col_name] = series_by_param[col_name].combine_first(s)
                else:
                    series_by_param[col_name] = s

        if not series_by_param:
            return pd.DataFrame()

        df_combined = pd.DataFrame(series_by_param)
        df_combined = df_combined.sort_index()
        return df_combined

    def build_extended_dataset(
        self,
        start_year: int = 2023,
        end_year: int = 2026,
    ) -> pd.DataFrame:
        """
        Executes end-to-end ingestion, cleaning, hourly resampling,
        and alignment with real precipitation.
        """
        logger.info("Executing Extended Multi-Year Ingestion (%d to %d)...", start_year, end_year)

        # 1. Fetch and parse all USGS years
        yearly_dfs = []
        for yr in range(start_year, end_year + 1):
            raw_usgs = self.fetch_usgs_year(yr)
            df_yr = self.parse_usgs_time_series(raw_usgs)
            if not df_yr.empty:
                yearly_dfs.append(df_yr)

        if not yearly_dfs:
            raise RuntimeError("Failed to retrieve any USGS data for extended period.")

        df_usgs_all = pd.concat(yearly_dfs).sort_index()
        df_usgs_all = df_usgs_all[~df_usgs_all.index.duplicated(keep="first")]
        logger.info("Combined raw USGS records: %d rows from %s to %s", len(df_usgs_all), df_usgs_all.index.min(), df_usgs_all.index.max())

        # 2. Resample USGS to regular 1-hour resolution
        cleaner = DataCleaner()
        df_cleaned, _ = cleaner.clean_timeseries(df_usgs_all, station_id=self.SITE_ID)

        resampler = DataResampler()
        df_hourly_usgs = resampler.resample(df_cleaned, target_resolution="1h")
        logger.info("Resampled USGS to 1h resolution: %d rows", len(df_hourly_usgs))

        # 3. Fetch Open-Meteo precipitation (ERA5-Land reanalysis, forced refresh to ensure explicit model & rain variable)
        raw_precip = self.fetch_openmeteo_precipitation(
            start_date=f"{start_year}-01-01",
            end_date="2026-09-28",
            force_refresh=True,
        )
        hourly_data = raw_precip["data"].get("hourly", {})
        precip_times = pd.to_datetime(hourly_data.get("time", []), utc=True)
        precip_vals = hourly_data.get("precipitation", [])
        rain_vals = hourly_data.get("rain", [])

        df_precip = pd.DataFrame({
            "rain_mm": rain_vals,
            "precipitation_mm": precip_vals,
        }, index=precip_times)
        df_precip = df_precip[~df_precip.index.duplicated(keep="first")]

        # 4. Temporal Alignment (join on UTC hourly timestamp)
        # SCIENTIFIC INTEGRITY CORRECTION:
        # DO NOT fill missing precipitation with 0.0.
        # Observed precipitation = 0.0 mm must be strictly distinguished from missing precipitation = NaN.
        # Open-Meteo explicitly provides 0.0 for dry hours; any timestamps lacking meteorological records
        # must remain NaN.
        # GEOGRAPHIC REPRESENTATION NOTE:
        # Precipitation values represent weather/reanalysis estimates at the monitoring station coordinates
        # (Lat 39.96779, Lon -75.18850) and are NOT automatically equivalent to watershed-average rainfall
        # across the 1,893 sq mi Schuylkill River drainage basin.
        df_extended = df_hourly_usgs.join(df_precip, how="left")

        # Re-insert timestamp column for compatibility
        df_extended = df_extended.reset_index().rename(columns={"index": "timestamp"})

        # 5. Save processed extended dataset
        out_csv = self.processed_dir / "station_01474500_extended_1h.csv"
        df_extended.to_csv(out_csv, index=False)
        logger.info(
            "Saved processed extended dataset to %s (%d rows, %s to %s)",
            out_csv,
            len(df_extended),
            df_extended["timestamp"].min(),
            df_extended["timestamp"].max(),
        )

        return df_extended


if __name__ == "__main__":
    ingestor = ExtendedDataIngestor()
    ingestor.build_extended_dataset()
