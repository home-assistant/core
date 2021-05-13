"""Constants for the AVM FRITZ!SmartHome integration."""
import logging
from typing import Final

ATTR_STATE_BATTERY_LOW: Final = "battery_low"
ATTR_STATE_DEVICE_LOCKED: Final = "device_locked"
ATTR_STATE_HOLIDAY_MODE: Final = "holiday_mode"
ATTR_STATE_LOCKED: Final = "locked"
ATTR_STATE_SUMMER_MODE: Final = "summer_mode"
ATTR_STATE_WINDOW_OPEN: Final = "window_open"

ATTR_TEMPERATURE_UNIT: Final = "temperature_unit"

ATTR_TOTAL_CONSUMPTION: Final = "total_consumption"
ATTR_TOTAL_CONSUMPTION_UNIT: Final = "total_consumption_unit"

CONF_CONNECTIONS: Final = "connections"
CONF_COORDINATOR: Final = "coordinator"

DEFAULT_HOST: Final = "fritz.box"
DEFAULT_USERNAME: Final = "admin"

DOMAIN: Final = "fritzbox"

LOGGER: logging.Logger = logging.getLogger(__package__)

PLATFORMS: Final = ["binary_sensor", "climate", "switch", "sensor"]
