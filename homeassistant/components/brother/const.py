"""Constants for Brother integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "brother"

PRINTER_TYPES: Final = ["laser", "ink"]

SNMP: Final = "snmp"

UPDATE_INTERVAL = timedelta(seconds=30)
