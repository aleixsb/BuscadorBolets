"""Command line utilities for interacting with the Meteocat API.

This module bundles the helpers to collect both precipitation and wind
measurements from Meteocat.  The previous implementation kept the wind
command line entry point in a dedicated module which duplicated most of the
argument parsing logic.  By consolidating everything in a single place we
ensure both datasets share the same defaults and reduce maintenance effort.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import logging
import os
from pathlib import Path
from typing import Iterable, List, Optional

from .aggregations import aggregate_precipitation
from .client import MeteocatClient
from .wind import DEFAULT_WIND_VARIABLES, collect_daily_wind_data

LOGGER = logging.getLogger(__name__)


def _parse_date(value: Optional[str], *, default: Optional[_dt.date] = None) -> _dt.date:
    if value:
        return _dt.date.fromisoformat(value)
    if default is not None:
        return default
    raise ValueError("Date value required")


def _default_start_date(today: _dt.date) -> _dt.date:
    august_first = _dt.date(year=today.year, month=8, day=1)
    if today >= august_first:
        return august_first
    return _dt.date(year=today.year - 1, month=8, day=1)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
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


def collect_rainfall(
    *,
    api_key: str,
    start_date: _dt.date,
    end_date: _dt.date,
    station_status: Optional[str] = None,
    network: Optional[str] = "XEMA",
    variable_code: str | int = 35,
) -> List[dict]:
    client = MeteocatClient(api_key)
    stations = client.list_stations(status=station_status, network=network)
    series: List[dict] = []

    for station in stations:
        code = (
            station.get("codi")
            or station.get("codiEstacio")
            or station.get("code")
            or station.get("id")
        )
        if not code:
            continue
        name = station.get("nom") or station.get("name")
        LOGGER.info("Downloading precipitation for %s (%s)", code, name or "unknown")
        try:
            daily = client.fetch_daily_precipitation(
                code,
                start_date=start_date,
                end_date=end_date,
                variable_code=variable_code,
            )
        except Exception as exc:  # noqa: BLE001 - we want to surface the station in logs
            LOGGER.error("Failed to download precipitation for %s: %s", code, exc)
            continue
        aggregates = aggregate_precipitation(daily)
        series.append(
            {
                "station": {
                    "code": code,
                    "name": name,
                    "municipality": station.get("municipi", {}).get("nom")
                    if isinstance(station.get("municipi"), dict)
                    else station.get("municipi")
                    or station.get("municipio"),
                    "coordinates": station.get("coordenades") or station.get("coordinates"),
                    "elevation": station.get("quota") or station.get("altitud"),
                },
                "daily": daily,
                "aggregated": aggregates,
            }
        )
    return series


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download datasets from Meteocat")
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ...).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    rainfall = subparsers.add_parser(
        "rainfall", help="Download precipitation data as JSON aggregations"
    )
    _add_shared_arguments(rainfall)
    rainfall.add_argument(
        "--variable-code",
        dest="variable_code",
        default="35",
        help="Variable code to use for precipitation (default: 35).",
    )
    rainfall.add_argument(
        "--output",
        dest="output",
        type=Path,
        required=True,
        help="Destination file where the JSON payload will be stored.",
    )

    wind = subparsers.add_parser(
        "wind", help="Download wind data as a CSV file"
    )
    _add_shared_arguments(wind)
    wind.add_argument(
        "--variable",
        dest="variables",
        action="append",
        help="Wind variable code to download (can be repeated, defaults to VV10m and DV10m)",
    )
    wind.add_argument(
        "--output",
        dest="output",
        type=Path,
        default=Path("data/wind_daily.csv"),
        help="Output CSV path (default: data/wind_daily.csv)",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if not getattr(args, "api_key", None):
        parser.error("An API key must be provided via --api-key or METEOCAT_API_KEY")

    today = _dt.date.today()
    start_date = _parse_date(args.start_date, default=_default_start_date(today))
    end_date = _parse_date(args.end_date, default=today)
    if start_date > end_date:
        parser.error("start-date must be before end-date")

    if args.command == "rainfall":
        series = collect_rainfall(
            api_key=args.api_key,
            start_date=start_date,
            end_date=end_date,
            station_status=args.station_status,
            network=args.network,
            variable_code=args.variable_code,
        )

        payload = {
            "generated_at": _dt.datetime.utcnow().isoformat() + "Z",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "station_count": len(series),
            "series": series,
        }

        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        LOGGER.info("Stored rainfall dataset at %s", output_path)
        return

    if args.command == "wind":
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
        return

    parser.error(f"Unsupported command: {args.command}")


def _write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
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


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
