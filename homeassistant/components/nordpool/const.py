"""Constants for Nord Pool."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DEFAULT_SCAN_INTERVAL = 60
DOMAIN = "nordpool"
PLATFORMS = [Platform.SENSOR]
DEFAULT_NAME = "Nord Pool"

CONF_AREAS = "areas"
