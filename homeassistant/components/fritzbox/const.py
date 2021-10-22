"""Constants for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

import logging
from typing import Final

ATTR_STATE_BATTERY_LOW: Final = "battery_low"
ATTR_STATE_DEVICE_LOCKED: Final = "device_locked"
ATTR_STATE_HOLIDAY_MODE: Final = "holiday_mode"
ATTR_STATE_LOCKED: Final = "locked"
ATTR_STATE_NEXTCHANGE_ENDPERIOD: Final = "nextchange_endperiod"
ATTR_STATE_NEXTCHANGE_PRESET_MODE: Final = "nextchange_preset_mode"
ATTR_STATE_NEXTCHANGE_TEMPERATURE: Final = "nextchange_temperature"
ATTR_STATE_SUMMER_MODE: Final = "summer_mode"
ATTR_STATE_TEMPERATURE_COMFORT: Final = "temperature_comfort"
ATTR_STATE_TEMPERATURE_ECO: Final = "temperature_eco"
ATTR_STATE_WINDOW_OPEN: Final = "window_open"

COLOR_MODE: Final = "1"
COLOR_TEMP_MODE: Final = "4"

CONF_CONNECTIONS: Final = "connections"
CONF_COORDINATOR: Final = "coordinator"

DEFAULT_HOST: Final = "fritz.box"
DEFAULT_USERNAME: Final = "admin"

DOMAIN: Final = "fritzbox"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

PLATFORMS: Final[list[str]] = ["binary_sensor", "climate", "light", "switch", "sensor"]
