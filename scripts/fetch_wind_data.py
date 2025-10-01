"""CLI entry point to download Meteocat wind data."""

from __future__ import annotations

import sys

from meteocat.wind_cli import main


if __name__ == "__main__":
    sys.exit(main())

