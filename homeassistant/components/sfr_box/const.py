"""SFR Box constants."""
from homeassistant.const import Platform

DEFAULT_HOST = "192.168.0.1"
DEFAULT_USERNAME = "admin"

DOMAIN = "sfr_box"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
PLATFORMS_WITH_AUTH = [*PLATFORMS, Platform.BUTTON]
