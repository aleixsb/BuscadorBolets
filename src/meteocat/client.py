"""HTTP client for the Meteocat API."""

from __future__ import annotations

import datetime as _dt
import logging
import time
from typing import Dict, Iterable, List, Optional

import requests

LOGGER = logging.getLogger(__name__)


class MeteocatClient:
    """Minimal wrapper around the Meteocat public API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.meteocat.gencat.cat/xema/v1",
        session: Optional[requests.Session] = None,
        request_timeout: int = 30,
        max_retries: int = 3,
        retry_wait: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.session.headers.update({"x-api-key": api_key})
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_wait = retry_wait

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_stations(self, *, status: str | None = None, network: str | None = None) -> List[Dict]:
        """Return the available observation stations.

        Parameters
        ----------
        status:
            Filter by station status (``"operativa"``, ``"tancada"`` or similar).
        network:
            Filter by network code. For example ``"XEMA"``.
        """

        params: Dict[str, str | int] = {"limit": 5000}
        if status:
            params["estat"] = status
        if network:
            params["xarxa"] = network

        payload = self._request_json("GET", "/estacions/metadades", params=params)
        stations = self._extract_list(payload, default_key="estacions")
        LOGGER.info("Loaded %s stations", len(stations))
        return stations

    def fetch_daily_precipitation(
        self,
        station_code: str,
        *,
        start_date: _dt.date,
        end_date: _dt.date,
        variable_code: str | int = 35,
        chunk_size: int = 31,
    ) -> List[Dict[str, object]]:
        """Fetch the daily precipitation accumulation for a station.

        The Meteocat API typically exposes daily accumulation under variable
        code ``35`` (``precipitacio``). If your account uses a different code
        you can override it through ``variable_code``.
        """

        results: List[Dict[str, object]] = []
        current = start_date
        while current <= end_date:
            chunk_end = min(current + _dt.timedelta(days=chunk_size - 1), end_date)
            params = {
                "codiEstacio": station_code,
                "dataInici": current.isoformat(),
                "dataFi": chunk_end.isoformat(),
                "variables": str(variable_code),
            }
            payload = self._request_json("GET", "/dades/diaries", params=params)
            chunk_results = self._extract_precipitation_series(payload, variable_code)
            LOGGER.debug(
                "Fetched %s records for %s between %s and %s",
                len(chunk_results),
                station_code,
                current,
                chunk_end,
            )
            results.extend(chunk_results)
            current = chunk_end + _dt.timedelta(days=1)
        results.sort(key=lambda entry: entry.get("date"))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request_json(self, method: str, path: str, *, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    timeout=self.request_timeout,
                )
                if response.status_code == 429:
                    wait_time = self.retry_wait * attempt
                    LOGGER.warning("Rate limited by Meteocat, sleeping for %ss", wait_time)
                    time.sleep(wait_time)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                if attempt > self.max_retries:
                    LOGGER.error("Meteocat request failed permanently: %s", exc)
                    raise
                wait_time = self.retry_wait * attempt
                LOGGER.warning(
                    "Request to %s failed with %s, retrying in %.1fs", url, exc, wait_time
                )
                time.sleep(wait_time)
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    LOGGER.error("Network error talking to Meteocat: %s", exc)
                    raise
                wait_time = self.retry_wait * attempt
                LOGGER.warning(
                    "Network error on %s (%s), retrying in %.1fs", url, exc, wait_time
                )
                time.sleep(wait_time)
        return {}

    @staticmethod
    def _extract_list(payload: object, *, default_key: str) -> List[Dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            if default_key in payload and isinstance(payload[default_key], list):
                return [item for item in payload[default_key] if isinstance(item, dict)]
            for key, value in payload.items():
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_precipitation_series(payload: object, variable_code: str | int) -> List[Dict[str, object]]:
        records: List[Dict[str, object]] = []
        candidates: Iterable = []
        if isinstance(payload, dict):
            for key in ("dades", "datos", "series", "resultats", "resultados"):
                if isinstance(payload.get(key), list):
                    candidates = payload[key]
                    break
            else:
                if isinstance(payload.get("lectures"), list):
                    candidates = payload["lectures"]
        elif isinstance(payload, list):
            candidates = payload

        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            date = entry.get("data") or entry.get("dia") or entry.get("date")
            value = (
                entry.get("valor")
                or entry.get("precipitacio")
                or entry.get("precipitacio24h")
                or entry.get("acumulat")
            )
            if value is None and isinstance(entry.get("variables"), list):
                for variable in entry["variables"]:
                    if not isinstance(variable, dict):
                        continue
                    code = variable.get("codi") or variable.get("code")
                    name = variable.get("nom") or variable.get("name", "")
                    if str(code) == str(variable_code) or "precip" in str(name).lower():
                        value = variable.get("valor") or variable.get("value")
                        if value is None and isinstance(variable.get("lectures"), list):
                            for lecture in variable["lectures"]:
                                if isinstance(lecture, dict) and lecture.get("valor") is not None:
                                    value = lecture.get("valor")
                                    break
                        break
            if not date or value is None:
                continue
            try:
                float_value = float(value)
            except (TypeError, ValueError):
                continue
            records.append({"date": str(date)[:10], "value": float_value})
        return records
