"""Constants for the Besen integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "besen"
NAME: Final = "Besen"

PLATFORMS: Final = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
