"""Constants for the Schlage integration."""

from datetime import timedelta
import logging

DOMAIN = "schlage"
LOGGER = logging.getLogger(__package__)
MANUFACTURER = "Schlage"
UPDATE_INTERVAL = timedelta(seconds=30)
