"""Constants for the PurpleAir integration."""

import logging
from typing import Final

DOMAIN: Final = "purpleair"

LOGGER: Final = logging.getLogger(__package__)

SCHEMA_VERSION: Final = 2

CONF_SENSOR_INDICES: Final = "sensor_indices"  # Deprecated in v2 schema
CONF_SENSOR_LIST: Final = "sensor_list"
CONF_SENSOR_INDEX: Final = "sensor_index"
CONF_SENSOR_READ_KEY: Final = "sensor_read_key"
