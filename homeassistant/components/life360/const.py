"""Constants for Life360 integration."""

from datetime import timedelta
import logging

DOMAIN = "life360"
LOGGER = logging.getLogger(__package__)

ATTRIBUTION = "Data provided by life360.com"
COMM_MAX_RETRIES = 2
COMM_TIMEOUT = 3.05
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
CONF_CIRCLES = "circles"
CONF_DRIVING_SPEED = "driving_speed"
CONF_ERROR_THRESHOLD = "error_threshold"
CONF_MAX_GPS_ACCURACY = "max_gps_accuracy"
CONF_MAX_UPDATE_WAIT = "max_update_wait"
CONF_MEMBERS = "members"
CONF_SHOW_AS_STATE = "show_as_state"
CONF_WARNING_THRESHOLD = "warning_threshold"

SHOW_DRIVING = "driving"
SHOW_MOVING = "moving"

DEFAULT_OPTIONS = {
    CONF_DRIVING_SPEED: None,
    CONF_MAX_GPS_ACCURACY: None,
    SHOW_DRIVING: False,
}
OPTIONS = list(DEFAULT_OPTIONS.keys())
