"""Constants for the AVM Fritz!Box integration."""
import logging

ATTR_STATE_BATTERY_LOW = "battery_low"
ATTR_STATE_DEVICE_LOCKED = "device_locked"
ATTR_STATE_HOLIDAY_MODE = "holiday_mode"
ATTR_STATE_LOCKED = "locked"
ATTR_STATE_SUMMER_MODE = "summer_mode"
ATTR_STATE_WINDOW_OPEN = "window_open"

ATTR_TEMPERATURE_UNIT = "temperature_unit"

ATTR_TOTAL_CONSUMPTION = "total_consumption"
ATTR_TOTAL_CONSUMPTION_UNIT = "total_consumption_unit"

CONF_CONNECTIONS = "connections"

DEFAULT_HOST = "fritz.box"
DEFAULT_USERNAME = "admin"

DOMAIN = "fritzbox"

LOGGER = logging.getLogger(__package__)

PLATFORMS = ["binary_sensor", "climate", "switch", "sensor"]
