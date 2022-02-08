"""Constants for Plugwise component."""
from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "plugwise"

LOGGER = logging.getLogger(__package__)

API = "api"
FLOW_SMILE = "smile (Adam/Anna/P1)"
FLOW_STRETCH = "stretch (Stretch)"
FLOW_TYPE = "flow_type"
GATEWAY = "gateway"
PW_TYPE = "plugwise_type"
SCHEDULE_OFF = "false"
SCHEDULE_ON = "true"
SMILE = "smile"
STRETCH = "stretch"
STRETCH_USERNAME = "stretch"
UNIT_LUMEN = "lm"

PLATFORMS_GATEWAY = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]
SENSOR_PLATFORMS = [Platform.SENSOR, Platform.SWITCH]
ZEROCONF_MAP = {
    "smile": "P1",
    "smile_thermo": "Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}


# Default directives
DEFAULT_MAX_TEMP = 30
DEFAULT_MIN_TEMP = 4
DEFAULT_NAME = "Smile"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = {
    "power": timedelta(seconds=10),
    "stretch": timedelta(seconds=60),
    "thermostat": timedelta(seconds=60),
}
DEFAULT_TIMEOUT = 60
DEFAULT_USERNAME = "smile"

# Configuration directives
CONF_GAS = "gas"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_POWER = "power"
CONF_THERMOSTAT = "thermostat"

# Icons
COOL_ICON = "mdi:snowflake"
FLAME_ICON = "mdi:fire"
FLOW_OFF_ICON = "mdi:water-pump-off"
FLOW_ON_ICON = "mdi:water-pump"
IDLE_ICON = "mdi:circle-off-outline"
SWITCH_ICON = "mdi:electric-switch"
NO_NOTIFICATION_ICON = "mdi:mailbox-outline"
NOTIFICATION_ICON = "mdi:mailbox-up-outline"
