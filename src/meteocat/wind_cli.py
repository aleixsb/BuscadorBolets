"""Command line helpers for downloading wind data from Meteocat."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import os
from pathlib import Path
from typing import Iterable, Mapping, Optional

from .wind import DEFAULT_WIND_VARIABLES, collect_daily_wind_data

LOGGER = logging.getLogger(__name__)


def _parse_date(value: Optional[str], *, default: Optional[dt.date] = None) -> dt.date:
    if value:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    if default is not None:
        return default
    raise ValueError("Date value required")


def _default_start_date(today: dt.date) -> dt.date:
    return dt.date(today.year, 8, 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download wind data from Meteocat")
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=os.environ.get("METEOCAT_API_KEY"),
        help="Meteocat API key. You can also use the METEOCAT_API_KEY environment variable.",
    )
    parser.add_argument(
        "--start-date",
        dest="start_date",
        help="ISO date (YYYY-MM-DD) for the first day to download. Defaults to 1st of August.",
    )
    parser.add_argument(
        "--end-date",
        dest="end_date",
        help="ISO date (YYYY-MM-DD) for the last day to download. Defaults to today.",
    )
    parser.add_argument(
        "--variable",
        dest="variables",
        action="append",
        help="Wind variable code to download (can be repeated, defaults to VV10m and DV10m)",
    )
    parser.add_argument(
        "--network",
        dest="network",
        default="XEMA",
        help="Station network to query (default: XEMA).",
    )
    parser.add_argument(
        "--station-status",
        dest="station_status",
        help="Optional status filter for the stations (e.g. operativa).",
    )
    parser.add_argument(
        "--output",
        dest="output",
        type=Path,
        default=Path("data/wind_daily.csv"),
        help="Output CSV path (default: data/wind_daily.csv)",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ...).",
    )
    return parser


def _write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        LOGGER.warning("No data rows to write")
        return
    field_names = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)
    LOGGER.info("Saved %d rows to %s", len(rows), path)


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if not args.api_key:
        parser.error("An API key must be provided via --api-key or METEOCAT_API_KEY")

    today = dt.date.today()
    start_date = _parse_date(args.start_date, default=_default_start_date(today))
    end_date = _parse_date(args.end_date, default=today)
    if start_date > end_date:
        parser.error("start-date must be before end-date")

    variables = args.variables or list(DEFAULT_WIND_VARIABLES)

    rows = collect_daily_wind_data(
        api_key=args.api_key,
        start_date=start_date,
        end_date=end_date,
        variables=variables,
        station_status=args.station_status,
        network=args.network,
    )

    _write_csv(args.output, rows)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

