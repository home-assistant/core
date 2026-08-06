"""Constants for the NeoPool integration."""

from homeassistant.const import Platform

DOMAIN = "neopool"
NAME = "NeoPool"

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 20  # in seconds
FOLLOW_UP_REFRESH_DELAY = 2.0  # seconds  (delay before a 2nd refresh for IO entity)
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

# Options-flow keys.
CONF_USE_LIGHT = "use_light"

CURRENT_VERSION = 6
