"""Utilities for working with the Meteocat public API."""

from .client import MeteocatClient
from .aggregations import aggregate_precipitation
from .wind import collect_daily_wind_data, DEFAULT_WIND_VARIABLES

__all__ = [
    "MeteocatClient",
    "aggregate_precipitation",
    "collect_daily_wind_data",
    "DEFAULT_WIND_VARIABLES",
]
