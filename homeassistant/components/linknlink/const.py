"""Constants for the LinknLink integration."""

from datetime import timedelta
import logging

DOMAIN = "linknlink"

DEFAULT_PORT = 80
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)

LOGGER = logging.getLogger(__package__)
