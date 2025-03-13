"""Constants for the PurpleAir integration."""

import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)
DOMAIN: Final[str] = "purpleair"

CONF_SENSOR_INDICES: Final[str] = "sensor_indices"

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
