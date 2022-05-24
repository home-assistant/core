"""Constants for Life360 integration."""

import logging

from homeassistant.components.device_tracker import CONF_SCAN_INTERVAL
from homeassistant.components.device_tracker.const import SCAN_INTERVAL
from homeassistant.const import CONF_PREFIX

DOMAIN = "life360"
LOGGER = logging.getLogger(__package__)

COMM_MAX_RETRIES = 2
COMM_TIMEOUT = 3.05
SPEED_FACTOR_MPH = 2.25
SPEED_DIGITS = 1
DEFAULT_SCAN_INTERVAL_TD = SCAN_INTERVAL
DEFAULT_SCAN_INTERVAL_SEC = DEFAULT_SCAN_INTERVAL_TD.total_seconds()

ATTR_ADDRESS = "address"
ATTR_AT_LOC_SINCE = "at_loc_since"
ATTR_DRIVING = "driving"
ATTR_LAST_SEEN = "last_seen"
ATTR_PLACE = "place"
ATTR_SPEED = "speed"
ATTR_WIFI_ON = "wifi_on"
ATTRIBUTION = "Data provided by life360.com"

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

OPTIONS = (
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    SHOW_DRIVING,
)
