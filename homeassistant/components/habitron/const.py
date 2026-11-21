"""Constants for the Habitron integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "habitron"
CONF_DEFAULT_HOST = "local"  # Hub on Home Assistant's own machine

SCAN_INTERVAL: Final = timedelta(seconds=10)
