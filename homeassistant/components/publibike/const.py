"""Constants for the PubliBike component."""

from datetime import timedelta

DOMAIN = "publibike"

BATTERY_LIMIT = "battery_limit"
BATTERY_LIMIT_DEFAULT = 1
LATITUDE = "latitude"
LONGITUDE = "longitude"
STATION_ID = "station_id"

UPDATE_INTERVAL = timedelta(minutes=1)
