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

# Internal key the sensor platform's import handler uses to hand pre-validated
# stops to the main flow's import step, to be created atomically as subentries.
CONF_SUBENTRIES: Final = "subentries"

DATA_FAILED_IMPORT_STOPS: Final = "failed_import_stops"

# Serializes the whole import body across concurrent YAML platform blocks so
# overlapping stops can't race past validation together.
DATA_IMPORT_LOCK: Final = "import_lock"

DEFAULT_NUMBER_OF_DEPARTURES: Final = 5

SCAN_INTERVAL: Final = timedelta(seconds=60)

MANUFACTURER: Final = "De Lijn"

SUBENTRY_TYPE_STOP: Final = "stop"
