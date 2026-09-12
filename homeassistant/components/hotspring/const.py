"""Constants for the Hot Spring integration."""

from datetime import timedelta
import logging

DOMAIN = "hotspring"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=30)
