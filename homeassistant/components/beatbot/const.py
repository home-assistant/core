"""Constants for the Beatbot integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "beatbot"

PLATFORMS: Final = [Platform.SENSOR]

NETWORK_REFRESH_INTERVAL: Final = 10 * 60
