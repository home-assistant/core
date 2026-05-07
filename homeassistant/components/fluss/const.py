"""Constants for the Fluss+ integration."""

from datetime import timedelta
import logging

DOMAIN = "fluss"
LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=30)
# Debouncer cooldown for coordinator refreshes triggered after a cover
# command — gives the device time to physically move before re-querying.
COMMAND_REFRESH_COOLDOWN = 10
