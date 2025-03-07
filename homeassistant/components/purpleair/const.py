"""Constants for the PurpleAir integration."""

import logging
from typing import Final

from homeassistant.const import Platform

LOGGER: Final = logging.getLogger(__package__)
PLATFORMS: Final = [Platform.SENSOR]

DOMAIN: Final = "purpleair"
RADIUS_DEFAULT: Final = 2000
UPDATE_INTERVAL: Final = 2
TITLE: Final = "PurpleAir"
MANUFACTURER = "PurpleAir, Inc."
LIMIT_RESULTS: Final = 25

SCHEMA_VERSION: Final = 2

CONF_SELECT_SENSOR: Final = "select_sensor"
CONF_MAP_LOCATION: Final = "map_location"
CONF_NEARBY_SENSOR_LIST: Final = "nearby_sensor_list"
CONF_SENSOR_LIST: Final = "sensor_list"
CONF_SENSOR_INDEX: Final = "sensor_index"
CONF_SENSOR_READ_KEY: Final = "sensor_read_key"
CONF_USER: Final = "user"
CONF_REAUTH_CONFIRM: Final = "reauth_confirm"
CONF_REMOVE_SENSOR: Final = "remove_sensor"
CONF_INIT: Final = "init"
CONF_ADD_SENSOR: Final = "add_sensor"
CONF_ALREADY_CONFIGURED: Final = "already_configured"
CONF_SETTINGS: Final = "settings"
CONF_UNKNOWN: Final = "unknown"
CONF_BASE: Final = "base"
CONF_INVALID_API_KEY: Final = "invalid_api_key"
CONF_NO_SENSORS_FOUND: Final = "no_sensors_found"
CONF_NO_SENSOR_FOUND: Final = "no_sensor_found"

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
