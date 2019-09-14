"""Constants for the ecobee integration."""
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "ecobee"
DATA_ECOBEE_CONFIG = "ecobee_config"

CONF_HOLD_TEMP = "hold_temp"
CONF_INDEX = "index"
CONF_REFRESH_TOKEN = "refresh_token"

DEFAULT_HOLD_TEMP = False

ECOBEE_PLATFORMS = ["binary_sensor", "climate", "sensor", "weather"]
