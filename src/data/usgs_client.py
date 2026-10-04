"""
AquaRehearsal-X - USGS Water Data API Client
Stage 1: Real Data Foundation

Fetches real instantaneous values and station metadata from USGS Water Services REST API.
Strict scientific integrity: Never fabricates data. Raw responses are cached unchanged
with full provenance records.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

from src.config.settings import (
    PARAM_CODE_TO_COLUMN,
    RAW_DATA_DIR,
    USGS_IV_URL,
    USGS_PARAM_CODES,
    USGS_SITE_URL,
)
from src.utils.logger import logger


class USGSClient:
    """Client for retrieving real environmental data from USGS Water Services."""

    DEFAULT_HEADERS = {
        "User-Agent": "AquaRehearsal-X/1.0 (IEEE Hackathon 2026; academic research; contact@aquarehearsal.org)",
        "Accept": "application/json, text/plain, */*",
    }

    def __init__(self, raw_data_dir: Path = RAW_DATA_DIR, timeout: int = 60):
        self.raw_data_dir = Path(raw_data_dir)
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def fetch_iv_data(
        self,
        site_id: str,
        parameter_codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch instantaneous values from USGS IV REST Service.

        Args:
            site_id: 8 to 15-digit USGS station identifier (e.g. '01646500')
            parameter_codes: List of USGS parameter codes, default DO, temp, discharge, turbidity
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            period: ISO-8601 duration e.g. 'P30D' (mutually exclusive with start/end)
            force_refresh: If True, bypass cached raw files

        Returns:
            Dictionary containing raw API response and retrieval provenance.
        """
        if parameter_codes is None:
            parameter_codes = ["00300", "00010", "00060", "00076", "63680", "00065"]

        clean_site_id = str(site_id).strip()
        date_str = f"{start_date}_{end_date}" if start_date else (period or "all")
        cache_filename = f"usgs_{clean_site_id}_{date_str}.json"
        cache_path = self.raw_data_dir / cache_filename

        if cache_path.exists() and not force_refresh:
            logger.info("Loading cached raw USGS data from %s", cache_path)
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        params: Dict[str, str] = {
            "format": "json",
            "sites": clean_site_id,
            "parameterCd": ",".join(parameter_codes),
            "siteStatus": "all",
        }

        if start_date:
            params["startDT"] = start_date
        if end_date:
            params["endDT"] = end_date
        if period and not start_date:
            params["period"] = period

        logger.info(
            "Querying USGS IV API for site %s, params %s, range %s - %s...",
            clean_site_id,
            parameter_codes,
            start_date,
            end_date,
        )

        try:
            response = requests.get(USGS_IV_URL, params=params, headers=self.DEFAULT_HEADERS, timeout=self.timeout)
            response.raise_for_status()
            raw_data = response.json()
            endpoint_url = response.url
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Batch query for site %s failed (%s). Attempting per-parameter fallback...",
                clean_site_id,
                str(e),
            )
            # Fallback: query each parameter individually to retrieve available variables
            combined_series = []
            successful_params = []
            for p_code in parameter_codes:
                single_params = dict(params)
                single_params["parameterCd"] = p_code
                try:
                    resp_single = requests.get(USGS_IV_URL, params=single_params, headers=self.DEFAULT_HEADERS, timeout=self.timeout)
                    if resp_single.status_code == 200:
                        single_json = resp_single.json()
                        ts_list = single_json.get("value", {}).get("timeSeries", [])
                        if ts_list:
                            combined_series.extend(ts_list)
                            successful_params.append(p_code)
                except Exception:
                    continue

            if not combined_series:
                logger.error("USGS API request failed for all individual parameters at site %s: %s", clean_site_id, str(e))
                raise RuntimeError(f"Failed to retrieve data from USGS API for site {clean_site_id}: {e}")

            raw_data = {"value": {"timeSeries": combined_series}}
            endpoint_url = f"{USGS_IV_URL}?sites={clean_site_id}&params={','.join(successful_params)}"

        # Provenance tracking
        provenance = {
            "source": "USGS Water Services - Instantaneous Values (IV) API",
            "retrieval_date_utc": datetime.now(timezone.utc).isoformat(),
            "station_id": clean_site_id,
            "parameter_codes": parameter_codes,
            "requested_start_date": start_date,
            "requested_end_date": end_date,
            "requested_period": period,
            "api_endpoint": endpoint_url,
        }

        packaged_data = {
            "provenance": provenance,
            "data": raw_data,
        }

        # Save unchanged raw file
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(packaged_data, f, indent=2)
        logger.info("Saved raw unchanged USGS response to %s", cache_path)

        return packaged_data

    def fetch_site_metadata(self, site_id: str) -> Dict[str, Any]:
        """Fetch station metadata from USGS Site Service."""
        clean_site_id = str(site_id).strip()
        params = {
            "format": "rdb",
            "sites": clean_site_id,
            "siteOutput": "expanded",
            "seriesCatalogOutput": "true",
        }
        try:
            resp = requests.get(USGS_SITE_URL, params=params, headers=self.DEFAULT_HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            text = resp.text
        except requests.exceptions.RequestException as e:
            logger.warning("Could not fetch expanded site metadata from site service: %s", e)
            return {"station_id": clean_site_id, "status": "unavailable"}

        return {"station_id": clean_site_id, "raw_rdb": text}

    @staticmethod
    def parse_iv_response(payload: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Parses USGS JSON instantaneous response into a clean time-series DataFrame
        and extracted metadata.

        Returns:
            Tuple of (DataFrame indexed by UTC datetime, station_metadata dict)
        """
        raw_root = payload.get("data", payload)
        time_series_list = (
            raw_root.get("value", {}).get("timeSeries", [])
        )

        metadata: Dict[str, Any] = {
            "station_id": None,
            "station_name": None,
            "latitude": None,
            "longitude": None,
            "available_parameters": {},
            "provenance": payload.get("provenance", {}),
        }

        if not time_series_list:
            logger.warning("No timeSeries records found in USGS response.")
            return pd.DataFrame(), metadata

        dfs: List[pd.DataFrame] = []

        for ts in time_series_list:
            source_info = ts.get("sourceInfo", {})
            if metadata["station_id"] is None:
                site_code = source_info.get("siteCode", [{}])[0].get("value")
                metadata["station_id"] = site_code
                metadata["station_name"] = source_info.get("siteName")
                geo_loc = source_info.get("geoLocation", {}).get("geogLocation", {})
                metadata["latitude"] = geo_loc.get("latitude")
                metadata["longitude"] = geo_loc.get("longitude")

            var_info = ts.get("variable", {})
            param_code = var_info.get("variableCode", [{}])[0].get("value")
            var_name = var_info.get("variableName")
            unit_code = var_info.get("unit", {}).get("unitCode")

            canonical_name = PARAM_CODE_TO_COLUMN.get(param_code, f"param_{param_code}")
            metadata["available_parameters"][param_code] = {
                "canonical_name": canonical_name,
                "variable_name": var_name,
                "unit": unit_code,
            }

            values_list = ts.get("values", [{}])[0].get("value", [])
            if not values_list:
                continue

            records = []
            for item in values_list:
                dt_str = item.get("dateTime")
                val_str = item.get("value")
                qualifiers = item.get("qualifiers", [])

                # Parse value: USGS indicates missing/rejected observations with specific codes or non-numeric
                try:
                    val = float(val_str)
                    if val in (-999999.0, -9999.0, 999999.0):
                        val = np.nan
                except (ValueError, TypeError):
                    val = np.nan

                records.append({
                    "timestamp": dt_str,
                    canonical_name: val,
                    f"{canonical_name}_qualifiers": ",".join(qualifiers),
                })

            if records:
                series_df = pd.DataFrame(records)
                # Convert timestamps to UTC datetime
                series_df["timestamp"] = pd.to_datetime(series_df["timestamp"], utc=True)
                series_df = series_df.drop_duplicates(subset=["timestamp"], keep="last")
                series_df = series_df.set_index("timestamp")
                dfs.append(series_df)

        if not dfs:
            return pd.DataFrame(), metadata

        # Outer merge all parameter time series on the UTC timestamp index
        combined_df = dfs[0]
        for next_df in dfs[1:]:
            # If canonical column already exists (e.g. turbidity with different method codes), merge carefully
            overlap_cols = [c for c in next_df.columns if c in combined_df.columns]
            if overlap_cols:
                # Fill missing values from alternative method code
                for col in overlap_cols:
                    combined_df[col] = combined_df[col].combine_first(next_df[col])
                non_overlap = [c for c in next_df.columns if c not in overlap_cols]
                if non_overlap:
                    combined_df = combined_df.join(next_df[non_overlap], how="outer")
            else:
                combined_df = combined_df.join(next_df, how="outer")

        combined_df = combined_df.sort_index()

        return combined_df, metadata
