"""Constants for the Zendure Smart Meter P1 integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "zendure_p1"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

UPDATE_INTERVAL = timedelta(seconds=5)
