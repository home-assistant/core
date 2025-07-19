"""Constants for the Velux integration."""

from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "velux"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SELECT,
]
LOGGER = getLogger(__package__)
