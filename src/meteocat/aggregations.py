"""Utilities for aggregating precipitation time series."""

from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from typing import Iterable, List, Dict, Tuple

DailyEntry = Dict[str, float | str | None]
AggregatedEntry = Dict[str, float | str]


def _normalize_date(value: str | _dt.date | _dt.datetime) -> _dt.date:
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    return _dt.date.fromisoformat(value[:10])


def _period_key(date: _dt.date, frequency: str) -> Tuple[int, int | None]:
    if frequency == "weekly":
        iso = date.isocalendar()
        return iso.year, iso.week
    if frequency == "monthly":
        return date.year, date.month
    if frequency == "yearly":
        return date.year, None
    raise ValueError(f"Unsupported frequency: {frequency}")


def _period_label(key: Tuple[int, int | None], frequency: str) -> str:
    year, second = key
    if frequency == "weekly" and second is not None:
        return f"{year}-W{int(second):02d}"
    if frequency == "monthly" and second is not None:
        return f"{year}-{int(second):02d}"
    if frequency == "yearly":
        return str(year)
    raise ValueError(f"Unsupported frequency: {frequency}")


def aggregate_precipitation(
    daily_data: Iterable[DailyEntry],
    *,
    frequencies: Iterable[str] = ("weekly", "monthly", "yearly"),
    value_key: str = "value",
    date_key: str = "date",
) -> Dict[str, List[AggregatedEntry]]:
    """Aggregate daily precipitation into several frequencies.

    Parameters
    ----------
    daily_data:
        An iterable of daily records. Each record must expose a value under
        ``value_key`` and a parseable ISO date under ``date_key``.
    frequencies:
        Iterable with the aggregation frequencies to compute. Supported values
        are ``"weekly"``, ``"monthly"`` and ``"yearly"``.
    value_key:
        Name of the key storing the precipitation value in millimetres.
    date_key:
        Name of the key storing the ISO formatted date.

    Returns
    -------
    dict
        A dictionary keyed by frequency that contains ordered lists of
        aggregated precipitation values.
    """

    normalized: List[Tuple[_dt.date, float]] = []
    for entry in daily_data:
        if entry is None:
            continue
        raw_date = entry.get(date_key) if isinstance(entry, dict) else None
        if not raw_date:
            continue
        try:
            date = _normalize_date(raw_date)
        except (TypeError, ValueError):
            continue
        raw_value = entry.get(value_key) if isinstance(entry, dict) else None
        if raw_value in (None, ""):
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        normalized.append((date, value))

    normalized.sort(key=lambda item: item[0])

    results: Dict[str, List[AggregatedEntry]] = {}
    for frequency in frequencies:
        totals: Dict[Tuple[int, int | None], float] = defaultdict(float)
        for date, value in normalized:
            key = _period_key(date, frequency)
            totals[key] += value
        aggregated = [
            {
                "period": _period_label(key, frequency),
                "value": round(total, 2),
            }
            for key, total in sorted(totals.items())
        ]
        results[frequency] = aggregated
    return results
