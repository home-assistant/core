"""Constants for the TechnoVE integration."""

from datetime import timedelta
import logging

DOMAIN = "technove"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)
