"""Constant for Imeon component."""

from homeassistant.const import Platform

DOMAIN = "imeon_inverter"
TIMEOUT = 10
INTERVAL = 60
PLATFORMS = [
    Platform.SENSOR,
]
