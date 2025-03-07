"""Constants for the PurpleAir integration."""

import logging
from typing import Final

DOMAIN: Final = "purpleair"

LOGGER: Final = logging.getLogger(__package__)

RADIUS_DEFAULT: Final = 2000
SCHEMA_VERSION: Final = 2

CONF_SELECT_SENSOR: Final = "select_sensor"
CONF_MAP_LOCATION: Final = "map_location"
CONF_NEARBY_SENSOR_LIST: Final = "nearby_sensor_list"
CONF_SENSOR_LIST: Final = "sensor_list"
CONF_SENSOR_INDEX: Final = "sensor_index"
CONF_SENSOR_READ_KEY: Final = "sensor_read_key"

SENSOR_FIELDS_TO_RETRIEVE: Final = [
    "0.3_um_count",
    "0.5_um_count",
    "1.0_um_count",
    "10.0_um_count",
    "2.5_um_count",
    "5.0_um_count",
    "altitude",
    "firmware_version",
    "hardware",
    "humidity",
    "latitude",
    "location_type",
    "longitude",
    "model",
    "name",
    "pm1.0",
    "pm10.0",
    "pm2.5",
    "pressure",
    "rssi",
    "temperature",
    "uptime",
    "voc",
]
