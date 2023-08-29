"""Constants for the Aqvify integration."""

from datetime import timedelta
import logging

DOMAIN = "aqvify"

CONF_DEVICE_KEY = "device_key"

LOGGER = logging.getLogger(__package__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
