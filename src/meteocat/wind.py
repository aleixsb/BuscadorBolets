"""Utilities for collecting wind information from Meteocat."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional

from .client import MeteocatClient

LOGGER = logging.getLogger(__name__)

DEFAULT_WIND_VARIABLES: tuple[str, ...] = ("VV10m", "DV10m")


@dataclass(frozen=True)
class Station:
    """Normalized representation of a Meteocat station."""

    code: str
    name: Optional[str]
    municipality: Optional[str]
    county: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[float]


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


def collect_daily_wind_data(
    *,
    api_key: str,
    start_date: dt.date,
    end_date: dt.date,
    variables: Iterable[str] = DEFAULT_WIND_VARIABLES,
    station_status: Optional[str] = None,
    network: Optional[str] = "XEMA",
) -> List[Mapping[str, object]]:
    """Collect the daily wind data for the given date range."""

    client = MeteocatClient(api_key)
    stations = client.list_stations(status=station_status, network=network)
    LOGGER.info("Retrieved %d stations", len(stations))
    variable_codes = list(dict.fromkeys(variables))

    all_records: List[Mapping[str, object]] = []
    for raw_station in stations:
        try:
            station = _normalize_station(raw_station)
        except KeyError as exc:
            LOGGER.debug("Skipping station with invalid metadata: %s", exc)
            continue
        LOGGER.info("Processing station %s (%s)", station.code, station.name or "unknown")
        daily_records: MutableMapping[str, Dict[str, object]] = {}
        for year, month in month_range(start_date, end_date):
            for variable_code in variable_codes:
                try:
                    entries = client.fetch_daily_variable_statistics(
                        station.code,
                        variable_code,
                        year=year,
                        month=month,
                    )
                except Exception as exc:  # pragma: no cover - network errors vary
                    LOGGER.warning(
                        "Skipping %s %s-%02d for %s due to API error: %s",
                        variable_code,
                        year,
                        month,
                        station.code,
                        exc,
                    )
                    continue
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        continue
                    date = _first_existing(entry, "data", "dia", "date")
                    if not date:
                        continue
                    value = _first_existing_optional(entry, "valor", "value")
                    record = daily_records.setdefault(
                        str(date),
                        {
                            "station_code": station.code,
                            "station_name": station.name,
                            "municipality": station.municipality,
                            "county": station.county,
                            "latitude": station.latitude,
                            "longitude": station.longitude,
                            "altitude": station.altitude,
                            "date": str(date),
                        },
                    )
                    record[variable_code] = value
        all_records.extend(sorted(daily_records.values(), key=lambda item: item["date"]))
    return all_records


def _normalize_station(raw: Mapping[str, object]) -> Station:
    code = _first_existing(raw, "codi", "codiEstacio", "codiXEMA", "code", "id")
    name = _first_existing_optional(raw, "nom", "nomEstacio", "descripcio", "name")
    municipality = _extract_nested_optional(raw, "municipi", "municipio", key="nom")
    county = _extract_nested_optional(raw, "comarca", key="nom")
    latitude = _safe_float(
        _first_existing_optional(
            raw,
            "latitud",
            "lat",
            "latitude",
            "coordenades.latitud",
            "coordinates.latitude",
        )
    )
    longitude = _safe_float(
        _first_existing_optional(
            raw,
            "longitud",
            "lon",
            "lng",
            "longitude",
            "coordenades.longitud",
            "coordinates.longitude",
        )
    )
    altitude = _safe_float(
        _first_existing_optional(raw, "altitud", "alt", "quota", "elevation")
    )
    return Station(
        code=code,
        name=name,
        municipality=municipality,
        county=county,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
    )


def _extract_nested_optional(
    entry: Mapping[str, object],
    *keys: str,
    key: str,
) -> Optional[str]:
    for candidate in keys:
        value = entry.get(candidate)
        if isinstance(value, Mapping):
            nested = value.get(key)
            if nested not in (None, ""):
                return str(nested)
        elif value not in (None, ""):
            return str(value)
    return None


def _first_existing(entry: Mapping[str, object], *keys: str) -> str:
    value = _first_existing_optional(entry, *keys)
    if value is None:
        raise KeyError(f"None of the keys {keys!r} found in entry {entry!r}")
    return value


def _first_existing_optional(entry: Mapping[str, object], *keys: str) -> Optional[str]:
    for key in keys:
        if "." in key:
            parent_key, child_key = key.split(".", 1)
            parent = entry.get(parent_key)
            if isinstance(parent, Mapping) and parent.get(child_key) not in (None, ""):
                return str(parent[child_key])
            continue
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

