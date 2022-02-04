"""Constants for Sensibo."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DEFAULT_SCAN_INTERVAL = 60
DOMAIN = "sensibo"
PLATFORMS = [Platform.CLIMATE]
ALL = ["all"]
DEFAULT_NAME = "Sensibo"
TIMEOUT = 8
