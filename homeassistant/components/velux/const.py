"""Constants for the Velux integration."""

from datetime import timedelta
from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "velux"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.COVER, Platform.LIGHT, Platform.SCENE]
LOGGER = getLogger(__package__)

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
