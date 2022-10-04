"""The Flume component."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "flume"

PLATFORMS = [Platform.SENSOR]

DEFAULT_NAME = "Flume Sensor"

NOTIFICATION_SCAN_INTERVAL = timedelta(minutes=1)
DEVICE_SCAN_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__package__)

FLUME_TYPE_SENSOR = 2

FLUME_AUTH = "flume_auth"
FLUME_HTTP_SESSION = "http_session"
FLUME_DEVICES = "devices"


CONF_TOKEN_FILE = "token_filename"
BASE_TOKEN_FILENAME = "FLUME_TOKEN_FILE"


KEY_DEVICE_TYPE = "type"
KEY_DEVICE_ID = "id"
KEY_DEVICE_LOCATION = "location"
KEY_DEVICE_LOCATION_NAME = "name"
KEY_DEVICE_LOCATION_TIMEZONE = "tz"
