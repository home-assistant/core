"""Constants for the Saunum Leil Sauna Control Unit integration."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "saunum"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
]

DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)
DELAYED_REFRESH_SECONDS: Final = timedelta(seconds=3)
