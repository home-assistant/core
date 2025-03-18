"""PurpleAir consts."""

import logging
from typing import Final

DOMAIN: Final[str] = "purpleair"
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
TITLE: Final[str] = "PurpleAir"
SCHEMA_VERSION: Final[int] = 2

CONF_ADD_MAP_LOCATION: Final[str] = "add_map_location"
CONF_ADD_OPTIONS: Final[str] = "add_options"
CONF_ADD_SENSOR_INDEX: Final[str] = "add_sensor_index"
CONF_ALREADY_CONFIGURED: Final[str] = "already_configured"
CONF_INVALID_API_KEY: Final[str] = "invalid_api_key"
CONF_NO_SENSOR_FOUND: Final[str] = "no_sensor_found"
CONF_NO_SENSORS_FOUND: Final[str] = "no_sensors_found"
CONF_REAUTH_CONFIRM: Final[str] = "reauth_confirm"
CONF_REAUTH_SUCCESSFUL: Final[str] = "reauth_successful"
CONF_RECONFIGURE_SUCCESSFUL: Final[str] = "reconfigure_successful"
CONF_RECONFIGURE: Final[str] = "reconfigure"
CONF_SELECT_SENSOR: Final[str] = "select_sensor"
CONF_SENSOR_INDEX: Final[str] = "sensor_index"
CONF_SENSOR_READ_KEY: Final[str] = "sensor_read_key"
CONF_SENSOR: Final[str] = "sensor"
CONF_SETTINGS: Final[str] = "settings"
CONF_UNKNOWN: Final[str] = "unknown"

SENSOR_FIELDS_ALL: Final[list[str]] = [
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
