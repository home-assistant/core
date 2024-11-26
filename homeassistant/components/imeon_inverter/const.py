"""Constant for Imeon component."""

from homeassistant.const import Platform

DOMAIN = "imeon_inverter"
HUBNAME = "imeon_inverter_hub"
TIMEOUT = 10  # seconds
PLATFORMS = [
    Platform.SENSOR,
]
