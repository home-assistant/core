"""Constants for the FENIX Control integration."""

from datetime import timedelta
import logging

DOMAIN = "fenix_control"
LOGGER = logging.getLogger(__package__)

SCAN_INTERVAL = timedelta(minutes=5)
