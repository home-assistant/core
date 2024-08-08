"""Constants for the swiss_public_transport integration."""

from typing import Final

DOMAIN = "swiss_public_transport"

CONF_DESTINATION: Final = "to"
CONF_START: Final = "from"
CONF_VIA: Final = "via"
CONF_TIME: Final = "time"
CONF_TIME_OFFSET: Final = "time_offset"
CONF_IS_ARRIVAL: Final = "is_arrival"

DEFAULT_NAME = "Next Destination"
DEFAULT_IS_ARRIVAL = False

MAX_VIA = 5
SENSOR_CONNECTIONS_COUNT = 3


PLACEHOLDERS = {
    "stationboard_url": "http://transport.opendata.ch/examples/stationboard.html",
    "opendata_url": "http://transport.opendata.ch",
}
