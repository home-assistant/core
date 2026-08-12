"""Constants for Google Wifi integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)
ATTR_CURRENT_VERSION = "current_version"
ATTR_LAST_RESTART = "last_restart"
ATTR_LOCAL_IP = "local_ip"
ATTR_NEW_VERSION = "new_version"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"
DEFAULT_HOST = "testwifi.here"
DEFAULT_NAME = "google_wifi"
ENDPOINT = "/api/v1/status"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)
