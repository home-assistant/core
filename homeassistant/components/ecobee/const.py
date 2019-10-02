"""Constants for the ecobee integration."""
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "ecobee"
DATA_ECOBEE_CONFIG = "ecobee_config"

CONF_INDEX = "index"
CONF_REFRESH_TOKEN = "refresh_token"

ECOBEE_MODEL_TO_NAME = {
    "idtSmart": "ecobee Smart",
    "idtEms": "ecobee Smart EMS",
    "siSmart": "ecobee Si Smart",
    "siEms": "ecobee Si EMS",
    "athenaSmart": "ecobee3 Smart",
    "athenaEms": "ecobee3 EMS",
    "corSmart": "Carrier/Bryant Cor",
    "nikeSmart": "ecobee3 lite Smart",
    "nikeEms": "ecobee3 lite EMS",
}

ECOBEE_PLATFORMS = ["binary_sensor", "climate", "sensor", "weather"]

MANUFACTURER = "ecobee"
