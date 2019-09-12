"""Constants for the ecobee integration."""
import logging

DOMAIN = "ecobee"
DATA_ECOBEE_CONFIG = "ecobee_config"

CONF_HOLD_TEMP = "hold_temp"
DEFAULT_HOLD_TEMP = False

CONF_REFRESH_TOKEN = "refresh_token"

ECOBEE_PLATFORMS = ["binary_sensor", "climate", "sensor", "weather"]

_LOGGER = logging.getLogger(__package__)
