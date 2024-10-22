"""Constants for the swiss_public_transport integration."""

from typing import Final

DOMAIN = "swiss_public_transport"

CONF_DESTINATION: Final = "to"
CONF_START: Final = "from"
CONF_VIA: Final = "via"
CONF_IS_ARRIVAL: Final = "is_arrival"
CONF_TIME_MODE: Final = "time_mode"
CONF_TIME: Final = "time"
CONF_TIME_OFFSET: Final = "time_offset"

DEFAULT_NAME = "Next Destination"
DEFAULT_UPDATE_TIME = 90
DEFAULT_IS_ARRIVAL = False
DEFAULT_TIME_MODE = "now"

MAX_VIA = 5
CONNECTIONS_COUNT = 3
CONNECTIONS_MAX = 15
TIME_MODE_OPTIONS = ["now", "fixed", "offset"]


PLACEHOLDERS = {
    "stationboard_url": "http://transport.opendata.ch/examples/stationboard.html",
    "opendata_url": "http://transport.opendata.ch",
}

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_LIMIT: Final = "limit"

SERVICE_FETCH_CONNECTIONS = "fetch_connections"
