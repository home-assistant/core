"""Constants for the israel rail integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "israel_rail"

CONF_DESTINATION: Final = "to"
CONF_START: Final = "from"

DEFAULT_NAME = "Next Destination"

SENSOR_CONNECTIONS_COUNT = 3

DEFAULT_SCAN_INTERVAL = timedelta(seconds=90)
