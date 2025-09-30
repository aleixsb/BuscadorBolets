"""Utilities for working with the Meteocat public API."""

from .client import MeteocatClient
from .aggregations import aggregate_precipitation

__all__ = ["MeteocatClient", "aggregate_precipitation"]
