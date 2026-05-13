"""Constants for the OpenAQ integration."""

import logging
from typing import Final

DOMAIN = "openaq"

LOGGER = logging.getLogger(__package__)

ATTRIBUTION: Final = "Data provided by OpenAQ"
CONF_LOCATION_ID: Final = "location_id"
CONF_RADIUS: Final = "radius"

MAX_RADIUS: Final = 25000
SUBENTRY_TYPE_LOCATION: Final = "location"
