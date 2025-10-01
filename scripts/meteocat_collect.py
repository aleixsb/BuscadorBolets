"""Unified CLI entry point for Meteocat dataset collection."""

from __future__ import annotations

import sys

from meteocat.cli import main


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())
