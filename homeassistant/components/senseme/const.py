"""Constants for the SenseME integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN = "senseme"

# Periodic fan update rate in minutes
UPDATE_RATE = 1

# data storage
CONF_INFO = "info"
CONF_HOST_MANUAL = "IP Address"
DISCOVERY = "discovery"

# Fan Preset Modes
PRESET_MODE_WHOOSH = "Whoosh"

# Fan Directions
SENSEME_DIRECTION_FORWARD = "FWD"
SENSEME_DIRECTION_REVERSE = "REV"


PLATFORMS = [Platform.FAN]
STARTUP_SCAN_TIMEOUT: Final = 5
DISCOVER_SCAN_TIMEOUT: Final = 10
DISCOVERY_INTERVAL: Final = timedelta(minutes=15)
