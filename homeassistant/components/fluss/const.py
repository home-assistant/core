"""Constants for the Fluss+ integration."""

from datetime import timedelta
import logging

DOMAIN = "fluss"
LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=30)
