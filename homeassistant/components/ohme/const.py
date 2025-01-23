"""Component constants."""

from homeassistant.const import Platform

DOMAIN = "ohme"
PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]
