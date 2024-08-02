"""Constants for the swiss_public_transport integration."""

from typing import Final

DOMAIN = "swiss_public_transport"

CONF_DESTINATION: Final = "to"
CONF_START: Final = "from"
CONF_VIA: Final = "via"

DEFAULT_NAME = "Next Destination"
DEFAULT_UPDATE_TIME = 90

MAX_VIA = 5
SENSOR_CONNECTIONS_COUNT = 3
SENSOR_CONNECTIONS_MAX = 15


PLACEHOLDERS = {
    "stationboard_url": "http://transport.opendata.ch/examples/stationboard.html",
    "opendata_url": "http://transport.opendata.ch",
}

ATTR_LIMIT: Final = "limit"

SERVICE_FETCH_CONNECTIONS = "fetch_connections"
