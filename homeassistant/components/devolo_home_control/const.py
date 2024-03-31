"""Constants for the devolo_home_control integration."""

import re

from homeassistant.const import Platform

DOMAIN = "devolo_home_control"
DEFAULT_MYDEVOLO = "https://www.mydevolo.com"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]
CONF_MYDEVOLO = "mydevolo_url"
GATEWAY_SERIAL_PATTERN = re.compile(r"\d{16}")
SUPPORTED_MODEL_TYPES = ["2600", "2601"]
