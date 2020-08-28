"""Constants for InfluxDB integration."""
from datetime import timedelta

DEFAULT_DATABASE = "home_assistant.rrd"
DOMAIN = "rrd"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
