"""Constants for the Saunum Leil Sauna Control Unit integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "saunum"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
]

DEFAULT_SCAN_INTERVAL: Final = 5
