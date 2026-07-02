"""Constants for the NeoPool integration."""

from homeassistant.const import Platform

DOMAIN = "neopool"
NAME = "NeoPool"

PLATFORMS: list[Platform] = [Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 20  # in seconds
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

CURRENT_VERSION = 6
