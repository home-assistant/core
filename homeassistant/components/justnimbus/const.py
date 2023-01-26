"""Constants for the JustNimbus integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN = "justnimbus"

VOLUME_FLOW_RATE_LITERS_PER_MINUTE: Final = "L/min"

PLATFORMS = [
    Platform.SENSOR,
]
