"""Define AirVisual constants."""
from datetime import timedelta

DOMAIN = "airvisual"

CONF_CITY = "city"
CONF_COUNTRY = "country"
CONF_STATIONS = "stations"

DATA_CLIENT = "client"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

TOPIC_OPTIONS_UPDATE = f"{DOMAIN}_options_update"
TOPIC_UPDATE = f"{DOMAIN}_update"
