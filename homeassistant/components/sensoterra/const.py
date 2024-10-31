"""Constants for the Sensoterra integration."""

import logging

DOMAIN = "sensoterra"
SCAN_INTERVAL_MINUTES = 15
SENSOR_EXPIRATION_DAYS = 2
TOKEN_EXPIRATION_DAYS = 10 * 365
CONFIGURATION_URL = "https://monitor.sensoterra.com"
LOGGER: logging.Logger = logging.getLogger(__package__)
