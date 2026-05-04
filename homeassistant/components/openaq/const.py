"""Constants for the OpenAQ integration."""

import logging
from typing import Final

DOMAIN = "openaq"

LOGGER = logging.getLogger(__package__)

ATTRIBUTION: Final = "Data provided by OpenAQ"
CONF_LIMIT: Final = "limit"
CONF_LOCATION_ID: Final = "location_id"
CONF_RADIUS: Final = "radius"

DEFAULT_LOCATION_LIMIT: Final = 25
DEFAULT_RADIUS: Final = 10000
MAX_RADIUS: Final = 25000
SUBENTRY_TYPE_LOCATION: Final = "location"
