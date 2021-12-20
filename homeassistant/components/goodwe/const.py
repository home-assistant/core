"""Constants for the Goodwe component."""
from datetime import timedelta

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

DOMAIN = "goodwe"

PLATFORMS = [NUMBER_DOMAIN, SELECT_DOMAIN, SENSOR_DOMAIN]

DEFAULT_NAME = "GoodWe"
SCAN_INTERVAL = timedelta(seconds=10)

CONF_MODEL_FAMILY = "model_family"

KEY_INVERTER = "inverter"
KEY_COORDINATOR = "coordinator"
KEY_DEVICE_INFO = "device_info"

INVERTER_OPERATION_MODES = [
    "General mode",
    "Off grid mode",
    "Backup mode",
    "Eco mode",
]
