"""PurpleAir consts."""

import logging
from typing import Final

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

DOMAIN: Final[str] = "purpleair"

SCHEMA_VERSION: Final[int] = 2

CONF_INVALID_API_KEY: Final[str] = "invalid_api_key"
CONF_SENSOR_INDEX: Final[str] = "sensor_index"
CONF_SENSOR_READ_KEY: Final[str] = "sensor_read_key"
CONF_SENSOR: Final[str] = "sensor"
CONF_UNKNOWN: Final[str] = "unknown"
TITLE: Final[str] = "PurpleAir"

SENSOR_FIELDS_TO_RETRIEVE: Final[list[str]] = [
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
