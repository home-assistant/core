"""Constants for pegel_online."""
from datetime import timedelta

DOMAIN = "pegel_online"

DEFAULT_RADIUS = "25"
CONF_STATION = "station"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
