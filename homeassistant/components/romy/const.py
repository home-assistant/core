"""Constants for the ROMY integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "romy"
ICON = "mdi:robot-vacuum"
PLATFORMS = [Platform.VACUUM]
UPDATE_INTERVAL = timedelta(seconds=5)
LOGGER = logging.getLogger(__package__)
