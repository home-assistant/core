"""Define constants for the Ambient PWS component."""
from functools import partial

DOMAIN = "ambient_station"

ATTR_LAST_DATA = "last_data"
ATTR_MONITORED_CONDITIONS = "monitored_conditions"

CONF_APP_KEY = "app_key"

DATA_CLIENT = "data_client"

TOPIC_UPDATE = partial("{domain}_update_{mac_address}", domain=DOMAIN)

TYPE_BINARY_SENSOR = "binary_sensor"
TYPE_SENSOR = "sensor"
