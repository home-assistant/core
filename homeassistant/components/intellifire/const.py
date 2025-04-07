"""Constants for the IntelliFire integration."""

from __future__ import annotations

import logging

DOMAIN = "intellifire"
LOGGER = logging.getLogger(__package__)
DEFAULT_THERMOSTAT_TEMP = 21

CONF_USER_ID = "user_id"  # part of the cloud cookie
CONF_WEB_CLIENT_ID = "web_client_id"  # part of the cloud cookie
CONF_AUTH_COOKIE = "auth_cookie"  # part of the cloud cookie

CONF_SERIAL = "serial"
CONF_READ_MODE = "cloud_read"
CONF_CONTROL_MODE = "cloud_control"


API_MODE_LOCAL = "local"
API_MODE_CLOUD = "cloud"


STARTUP_TIMEOUT = 600

INIT_WAIT_TIME_SECONDS = 10
