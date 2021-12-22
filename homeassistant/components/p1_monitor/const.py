"""Constants for the P1 Monitor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "p1_monitor"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)

SERVICE_SMARTMETER: Final = "smartmeter"
SERVICE_PHASES: Final = "phases"
SERVICE_SETTINGS: Final = "settings"

SERVICES: dict[str, str] = {
    SERVICE_SMARTMETER: "SmartMeter",
    SERVICE_PHASES: "Phases",
    SERVICE_SETTINGS: "Settings",
}
