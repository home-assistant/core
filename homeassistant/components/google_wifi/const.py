"""Constants for the Google Wifi integration."""

from __future__ import annotations

DOMAIN = "google_wifi"

# Attribute Keys
ATTR_CURRENT_VERSION = "current_version"
ATTR_LAST_RESTART = "last_restart"
ATTR_LOCAL_IP = "local_ip"
ATTR_NEW_VERSION = "new_version"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"
ATTR_GROUP_ROLE = "group_role"

#API Constants
ENDPOINT = "/api/v1/status"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)