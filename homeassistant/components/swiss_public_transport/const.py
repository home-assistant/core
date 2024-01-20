"""Constants for the swiss_public_transport integration."""

DOMAIN = "swiss_public_transport"

CONF_DESTINATION = "to"
CONF_START = "from"
CONF_RATE = "rate"

DEFAULT_NAME = "Next Destination"
DEFAULT_RATE = 90

PLACEHOLDERS = {
    "stationboard_url": "http://transport.opendata.ch/examples/stationboard.html",
    "opendata_url": "http://transport.opendata.ch",
}
