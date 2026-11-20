"""Constants for the Fluss+ integration."""

from datetime import timedelta
import logging

DOMAIN = "fluss"
LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(minutes=30)
COMMAND_REFRESH_COOLDOWN = 10
