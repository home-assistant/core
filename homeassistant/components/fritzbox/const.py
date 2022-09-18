"""Constants for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

ATTR_STATE_BATTERY_LOW: Final = "battery_low"
ATTR_STATE_HOLIDAY_MODE: Final = "holiday_mode"
ATTR_STATE_SUMMER_MODE: Final = "summer_mode"
ATTR_STATE_WINDOW_OPEN: Final = "window_open"

COLOR_MODE: Final = "1"
COLOR_TEMP_MODE: Final = "4"

CONF_CONNECTIONS: Final = "connections"
CONF_COORDINATOR: Final = "coordinator"

DEFAULT_HOST: Final = "fritz.box"
DEFAULT_USERNAME: Final = "admin"

DOMAIN: Final = "fritzbox"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

PLATFORMS: Final[list[Platform]] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
