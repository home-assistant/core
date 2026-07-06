"""Constants for the UptimeRobot integration."""

from datetime import timedelta
from logging import Logger, getLogger
from typing import Final

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

# The free plan is formally limited to 10 requests/minute
# But real world says 5 requests/minute is the real limit
# Opened a ticket with support with no response for 2 months
COORDINATOR_UPDATE_INTERVAL: timedelta = timedelta(seconds=15)

DOMAIN: Final = "uptimerobot"
PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

ATTRIBUTION: Final = "Data provided by UptimeRobot"

ATTR_TARGET: Final = "target"

API_ATTR_OK: Final = "ok"

STATUS_UP = "UP"
STATUS_DOWN = "DOWN"
STATUS_STARTED = "STARTED"

STATUSES_ON = [STATUS_UP, STATUS_STARTED]
