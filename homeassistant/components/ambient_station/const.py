"""Define constants for the Ambient PWS component."""
import logging

DOMAIN = "ambient_station"
LOGGER = logging.getLogger(__package__)

ATTR_LAST_DATA = "last_data"
ATTR_MONITORED_CONDITIONS = "monitored_conditions"

CONF_APP_KEY = "app_key"

DATA_CLIENT = "data_client"

TYPE_BINARY_SENSOR = "binary_sensor"
TYPE_SENSOR = "sensor"
