"""Constants for Sensibo."""

import logging
from homeassistant.const import Platform
from homeassistant.components.climate.const import (
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)

LOGGER = logging.getLogger(__package__)

DEFAULT_SCAN_INTERVAL = 60
DOMAIN = "sensibo"
PLATFORMS = [Platform.CLIMATE]
ALL = ["all"]
DEFAULT_NAME = "Sensibo"
TIMEOUT = 8
FIELD_TO_FLAG = {
    "fanLevel": SUPPORT_FAN_MODE,
    "swing": SUPPORT_SWING_MODE,
    "targetTemperature": SUPPORT_TARGET_TEMPERATURE,
}
