"""The Flume component."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "flume"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

DEFAULT_NAME = "Flume Sensor"

# Flume API limits individual endpoints to 120 queries per hour
NOTIFICATION_SCAN_INTERVAL = timedelta(minutes=1)
DEVICE_SCAN_INTERVAL = timedelta(minutes=1)
DEVICE_CONNECTION_SCAN_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__package__)

FLUME_TYPE_BRIDGE = 1
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


NOTIFICATION_HIGH_FLOW = "High Flow Alert"
NOTIFICATION_BRIDGE_DISCONNECT = "Bridge Disconnection"
BRIDGE_NOTIFICATION_KEY = "connected"
BRIDGE_NOTIFICATION_RULE = "Bridge Disconnection"
NOTIFICATION_LEAK_DETECTED = "Flume Smart Leak Alert"


def _filter_flume_devices(device_list: list, just_sensors: bool):
    """Filter flume devices."""
    if just_sensors:
        return [
            device
            for device in device_list
            if KEY_DEVICE_LOCATION_NAME in device[KEY_DEVICE_LOCATION]
            and device[KEY_DEVICE_TYPE] == FLUME_TYPE_SENSOR
        ]
    return [
        device
        for device in device_list
        if KEY_DEVICE_LOCATION_NAME in device[KEY_DEVICE_LOCATION]
    ]
