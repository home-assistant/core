"""Define constants for the Luftdaten component."""
from datetime import timedelta

ATTR_STATION_ID = "station_id"

CONF_STATION_ID = "station_id"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

DEFAULT_TIMEOUT = 10
DEFAULT_MAX_JOURNEYS = 5
DEFAULT_TIME_OFFSET = 0

DOMAIN = "rmvtransport"

CONF_STATION = "station"
CONF_DESTINATIONS = "destinations"
CONF_DIRECTION = "direction"
CONF_LINES = "lines"
CONF_PRODUCTS = "products"
CONF_TIME_OFFSET = "time_offset"
CONF_MAX_JOURNEYS = "max_journeys"
CONF_TIMEOUT = "timeout"
CONF_HASH = "conf_hash"

VALID_PRODUCTS = ["U-Bahn", "Tram", "Bus", "S", "RB", "RE", "EC", "IC", "ICE"]
