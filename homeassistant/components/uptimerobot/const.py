"""Constants for the Uptime Robot integration."""
from __future__ import annotations

from datetime import timedelta
from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

# The free plan is limited to 10 requests/minute
COORDINATOR_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)

DOMAIN: Final = "uptimerobot"
PLATFORMS: Final = ["binary_sensor"]

ATTRIBUTION: Final = "Data provided by Uptime Robot"

ATTR_TARGET: Final = "target"

API_ATTR_OK: Final = "ok"
