"""Constants for the De Lijn integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "delijn"

LOGGER = logging.getLogger(__package__)

CONF_STOP_NUMBER: Final = "stop_number"
CONF_NUMBER_OF_DEPARTURES: Final = "number_of_departures"

# Key used by the legacy YAML sensor platform schema, kept for import only.
CONF_STOP_ID: Final = "stop_id"

DEFAULT_NUMBER_OF_DEPARTURES: Final = 5

SCAN_INTERVAL: Final = timedelta(seconds=60)

MANUFACTURER: Final = "De Lijn"
