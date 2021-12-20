"""Constants for the Goodwe component."""
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

DOMAIN = "goodwe"

PLATFORMS = [NUMBER_DOMAIN, SELECT_DOMAIN, SENSOR_DOMAIN]

DEFAULT_NAME = "GoodWe"
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_NETWORK_RETRIES = 3
DEFAULT_NETWORK_TIMEOUT = 1

CONF_MODEL_FAMILY = "model_family"
CONF_NETWORK_RETRIES = "network_retries"
CONF_NETWORK_TIMEOUT = "network_timeout"

KEY_INVERTER = "inverter"
KEY_COORDINATOR = "coordinator"
KEY_DEVICE_INFO = "device_info"

INVERTER_OPERATION_MODES = [
    "General mode",
    "Off grid mode",
    "Backup mode",
    "Eco mode",
]
