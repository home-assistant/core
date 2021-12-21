"""Constants for the Goodwe component."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "goodwe"

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

DEFAULT_NAME = "GoodWe"
SCAN_INTERVAL = timedelta(seconds=10)

CONF_MODEL_FAMILY = "model_family"

KEY_INVERTER = "inverter"
KEY_COORDINATOR = "coordinator"
KEY_DEVICE_INFO = "device_info"
