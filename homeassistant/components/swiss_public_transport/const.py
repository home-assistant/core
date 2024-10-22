"""Constants for the swiss_public_transport integration."""

from typing import Final

DOMAIN = "swiss_public_transport"

CONF_DESTINATION: Final = "to"
CONF_START: Final = "from"
CONF_VIA: Final = "via"

DEFAULT_NAME = "Next Destination"
DEFAULT_UPDATE_TIME = 90
DEFAULT_DEPARTURE_MODE = "now"
DEFAULT_DEPARTURE_TIME = "00:00:00"
DEFAULT_DEPARTURE_TIME_OFFSET_MINUTES = 5

MAX_VIA = 5
CONNECTIONS_COUNT = 3
CONNECTIONS_MAX = 15
DEPARTURE_MODE_OPTIONS = ["now", "relative", "absolute"]


PLACEHOLDERS = {
    "stationboard_url": "http://transport.opendata.ch/examples/stationboard.html",
    "opendata_url": "http://transport.opendata.ch",
}

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_LIMIT: Final = "limit"

SERVICE_FETCH_CONNECTIONS = "fetch_connections"
