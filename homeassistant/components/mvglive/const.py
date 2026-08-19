"""Constants for the MVG integration."""

DOMAIN = "mvglive"

CONF_STATION = "station"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_DESTINATIONS = "destinations"
CONF_DIRECTIONS = "directions"
CONF_LINES = "lines"
CONF_PRODUCTS = "products"
CONF_TIMEOFFSET = "timeoffset"
CONF_NUMBER = "number"

DEFAULT_DESTINATIONS: list[str] = [""]
DEFAULT_LINES: list[str] = [""]
DEFAULT_PRODUCTS: list[str] | None = None
DEFAULT_TIMEOFFSET = 0
DEFAULT_NUMBER = 5
