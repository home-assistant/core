"""Constants for Life360 integration."""

from datetime import timedelta
import logging

from aiohttp import ClientTimeout

DOMAIN = "life360"
LOGGER = logging.getLogger(__package__)

ATTRIBUTION = "Data provided by life360.com"
COMM_MAX_RETRIES = 3
COMM_TIMEOUT = ClientTimeout(sock_connect=15, total=60)
SPEED_FACTOR_MPH = 2.25
SPEED_DIGITS = 1
UPDATE_INTERVAL = timedelta(seconds=10)

ATTR_ADDRESS = "address"
ATTR_AT_LOC_SINCE = "at_loc_since"
ATTR_DRIVING = "driving"
ATTR_LAST_SEEN = "last_seen"
ATTR_PLACE = "place"
ATTR_SPEED = "speed"
ATTR_WIFI_ON = "wifi_on"

CONF_AUTHORIZATION = "authorization"
CONF_DRIVING_SPEED = "driving_speed"
CONF_MAX_GPS_ACCURACY = "max_gps_accuracy"

SHOW_DRIVING = "driving"

DEFAULT_OPTIONS = {
    CONF_DRIVING_SPEED: None,
    CONF_MAX_GPS_ACCURACY: None,
    SHOW_DRIVING: False,
}
OPTIONS = list(DEFAULT_OPTIONS.keys())
