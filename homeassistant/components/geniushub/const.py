"""Constants for Genius Hub."""

from datetime import timedelta
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "geniushub"

ATTR_DURATION = "duration"

SCAN_INTERVAL = timedelta(seconds=60)

SENSOR_PREFIX = "Genius"

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
)


class GeniusHubService(StrEnum):
    """Store keys for Genius Hub services."""

    SET_ZONE_MODE = "set_zone_mode"
    SET_ZONE_OVERRIDE = "set_zone_override"
    SET_SWITCH_OVERRIDE = "set_switch_override"


class GeniusHubServiceArgument(StrEnum):
    """Store keys for Genius Hub service arguments."""

    MODE = "mode"
    TEMPERATURE = "temperature"
    DURATION = "duration"
