"""Constants for the israel rail integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "israel_rail"

CONF_START: Final = "from"
CONF_DESTINATION: Final = "to"

DEFAULT_NAME = "Next Destination"

DEPARTURES_COUNT = 3

DEFAULT_SCAN_INTERVAL = timedelta(seconds=90)

ATTRIBUTION = "Data provided by Israel rail."
