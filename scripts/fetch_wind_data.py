"""Download daily wind data from Meteocat's XEMA API.

This script retrieves the daily wind speed and direction aggregated values for
all the stations available in the Meteocat network starting from a given date
(defaults to the first day of August of the current year) up to an end date
(defaults to today). The collected data is stored as a CSV file containing one
row per station and day.

The script requires a Meteocat API key. You can obtain one from
https://apidocs.meteo.cat/. Provide it through the ``METEOCAT_API_KEY``
environment variable or via the ``--api-key`` command-line option.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional

import requests

BASE_URL = "https://api.meteocat.gencat.cat/xema/v1"
STATIONS_ENDPOINT = f"{BASE_URL}/estacions/metadades"
VARIABLE_ENDPOINT_TEMPLATE = (
    f"{BASE_URL}/dades/variables/{{variable}}/estadistica/diaria"
)

# Default wind related variable codes defined by Meteocat's XEMA API.
# ``VV10m`` - Mean wind speed at 10 metres (m/s)
# ``DV10m`` - Mean wind direction at 10 metres (degrees)
DEFAULT_WIND_VARIABLES = ("VV10m", "DV10m")

# According to Meteocat's documentation the recommended rate-limit is around
# 30 requests per minute for the XEMA API. We stay below that with 0.4 seconds
# between requests.
REQUEST_DELAY_SECONDS = 0.4

logger = logging.getLogger("meteocat_wind")


@dataclass(frozen=True)
class Station:
    """Container for the station metadata we care about."""

    code: str
    name: str
    municipality: Optional[str]
    county: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[float]


class MeteocatClient:
    """Small helper around the Meteocat XEMA API."""

    def __init__(self, api_key: str, *, session: Optional[requests.Session] = None):
        if not api_key:
            raise ValueError("API key must not be empty")
        self._session = session or requests.Session()
        self._session.headers.update({"Accept": "application/json", "x-api-key": api_key})

    def get_json(self, url: str, *, params: Optional[Mapping[str, object]] = None) -> Mapping:
        logger.debug("GET %s params=%s", url, params)
        response = self._session.get(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - network errors can vary
            logger.error("Request failed for %s with params=%s: %s", url, params, exc)
            raise
        time.sleep(REQUEST_DELAY_SECONDS)
        return response.json()

    def list_stations(self) -> List[Station]:
        payload = self.get_json(STATIONS_ENDPOINT)
        raw_stations: Iterable[Mapping] = _extract_station_entries(payload)
        stations: List[Station] = []
        for entry in raw_stations:
            code = _first_existing(entry, "codi", "codiXEMA", "codiEstacio")
            name = _first_existing(entry, "nom", "nomEstacio", "descripcio")
            municipality = _first_existing_optional(entry, "municipi", "municipiNom")
            county = _first_existing_optional(entry, "comarca", "comarcaNom")
            latitude = _safe_float(_first_existing_optional(entry, "latitud", "lat"))
            longitude = _safe_float(_first_existing_optional(entry, "longitud", "lon"))
            altitude = _safe_float(_first_existing_optional(entry, "altitud", "alt"))
            stations.append(
                Station(
                    code=code,
                    name=name,
                    municipality=municipality,
                    county=county,
                    latitude=latitude,
                    longitude=longitude,
                    altitude=altitude,
                )
            )
        return stations

    def get_daily_variable(
        self,
        *,
        station_code: str,
        variable_code: str,
        year: int,
        month: int,
    ) -> Iterable[Mapping[str, object]]:
        url = VARIABLE_ENDPOINT_TEMPLATE.format(variable=variable_code)
        params = {"codiEstacio": station_code, "any": year, "mes": month}
        payload = self.get_json(url, params=params)
        return _extract_data_entries(payload)


def _extract_station_entries(payload: Mapping) -> Iterable[Mapping]:
    """Return the iterable with the station entries from the payload."""

    if isinstance(payload, Mapping):
        if "metadades" in payload and isinstance(payload["metadades"], Iterable):
            return payload["metadades"]
        if "estacions" in payload and isinstance(payload["estacions"], Iterable):
            return payload["estacions"]
        if "stations" in payload and isinstance(payload["stations"], Iterable):
            return payload["stations"]
    raise ValueError("Unexpected station metadata payload format")


def _extract_data_entries(payload: Mapping) -> Iterable[Mapping]:
    """Return the iterable with the data entries from the payload."""

    if isinstance(payload, Mapping):
        if "dades" in payload and isinstance(payload["dades"], Iterable):
            return payload["dades"]
        if "series" in payload and isinstance(payload["series"], Iterable):
            return payload["series"]
    raise ValueError("Unexpected data payload format")


def _first_existing(entry: Mapping, *keys: str) -> str:
    for key in keys:
        value = entry.get(key)
        if value:
            return str(value)
    raise KeyError(f"None of the keys {keys!r} found in entry {entry!r}")


def _first_existing_optional(entry: Mapping, *keys: str) -> Optional[str]:
    for key in keys:
        value = entry.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def month_range(start: dt.date, end: dt.date) -> Iterator[tuple[int, int]]:
    """Yield the ``(year, month)`` tuples between ``start`` and ``end`` inclusive."""

    if start > end:
        raise ValueError("start must be before end")
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month == 13:
            month = 1
            year += 1


def build_default_start_date(today: Optional[dt.date] = None) -> dt.date:
    today = today or dt.date.today()
    return dt.date(today.year, 8, 1)


def collect_daily_wind_data(
    *,
    api_key: str,
    start_date: dt.date,
    end_date: dt.date,
    variables: Iterable[str] = DEFAULT_WIND_VARIABLES,
) -> List[Mapping[str, object]]:
    client = MeteocatClient(api_key)
    stations = client.list_stations()
    logger.info("Retrieved %d stations", len(stations))
    variable_codes = list(dict.fromkeys(variables))

    all_records: List[Mapping[str, object]] = []
    for station in stations:
        logger.info("Processing station %s (%s)", station.code, station.name)
        daily_records: MutableMapping[str, Dict[str, object]] = {}
        for year, month in month_range(start_date, end_date):
            for variable_code in variable_codes:
                try:
                    entries = client.get_daily_variable(
                        station_code=station.code,
                        variable_code=variable_code,
                        year=year,
                        month=month,
                    )
                except requests.HTTPError as exc:  # pragma: no cover
                    logger.warning(
                        "Skipping %s %s-%02d for %s due to API error: %s",
                        variable_code,
                        year,
                        month,
                        station.code,
                        exc,
                    )
                    continue
                for entry in entries:
                    date_str = _first_existing(entry, "data", "dia", "date")
                    value = entry.get("valor")
                    if value is None:
                        value = entry.get("value")
                    record = daily_records.setdefault(
                        date_str,
                        {
                            "station_code": station.code,
                            "station_name": station.name,
                            "municipality": station.municipality,
                            "county": station.county,
                            "latitude": station.latitude,
                            "longitude": station.longitude,
                            "altitude": station.altitude,
                            "date": date_str,
                        },
                    )
                    record[variable_code] = value
        all_records.extend(sorted(daily_records.values(), key=lambda item: item["date"]))
    return all_records


def write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        logger.warning("No data rows to write")
        return
    field_names = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Saved %d rows to %s", len(rows), path)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-key",
        help="Meteocat API key (defaults to METEOCAT_API_KEY environment variable)",
    )
    parser.add_argument(
        "--start-date",
        type=lambda value: dt.datetime.strptime(value, "%Y-%m-%d").date(),
        default=None,
        help="Start date in YYYY-MM-DD format (default: first day of August of the current year)",
    )
    parser.add_argument(
        "--end-date",
        type=lambda value: dt.datetime.strptime(value, "%Y-%m-%d").date(),
        default=None,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--variable",
        dest="variables",
        action="append",
        help="Wind variable code to download (can be repeated, defaults to VV10m and DV10m)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/wind_daily.csv"),
        help="Output CSV path (default: data/wind_daily.csv)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    api_key = args.api_key or os.environ.get("METEOCAT_API_KEY")
    if not api_key:
        logger.error("A Meteocat API key is required. Set METEOCAT_API_KEY or use --api-key.")
        return 1

    today = dt.date.today()
    start_date = args.start_date or build_default_start_date(today)
    end_date = args.end_date or today

    if start_date > end_date:
        logger.error("Start date must not be after end date")
        return 1

    variables = args.variables or list(DEFAULT_WIND_VARIABLES)

    logger.info(
        "Collecting daily wind data from %s to %s for %d variables",
        start_date,
        end_date,
        len(variables),
    )

    try:
        rows = collect_daily_wind_data(
            api_key=api_key,
            start_date=start_date,
            end_date=end_date,
            variables=variables,
        )
    except requests.HTTPError:
        return 1

    write_csv(args.output, rows)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
