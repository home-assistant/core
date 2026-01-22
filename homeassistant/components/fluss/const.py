"""Constants for the Fluss+ integration."""

from datetime import timedelta
import logging

DOMAIN = "fluss"
LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = 60  # seconds
UPDATE_INTERVAL_TIMEDELTA = timedelta(seconds=UPDATE_INTERVAL)
