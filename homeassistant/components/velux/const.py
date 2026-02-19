"""Constants for the Velux integration."""

from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "velux"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SWITCH,
]
LOGGER = getLogger(__package__)
