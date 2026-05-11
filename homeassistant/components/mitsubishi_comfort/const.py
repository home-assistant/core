"""Constants for the Mitsubishi Comfort integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mitsubishi_comfort"
PLATFORMS: Final = [Platform.CLIMATE]
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_CONNECT_TIMEOUT: Final = 1.2
DEFAULT_RESPONSE_TIMEOUT: Final = 8.0
