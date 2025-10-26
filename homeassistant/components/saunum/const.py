"""Constants for the Saunum Leil Sauna Control Unit integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "saunum"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
]

DEFAULT_SCAN_INTERVAL: Final = 5

# Value ranges - Fahrenheit (for display)
MIN_TEMPERATURE_F: Final = 104  # 40°C
MAX_TEMPERATURE_F: Final = 212  # 100°C
