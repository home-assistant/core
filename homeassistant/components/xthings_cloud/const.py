"""Constants for Xthings Cloud integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "xthings_cloud"
LOGGER = logging.getLogger(__package__)

CONF_REFRESH_TOKEN = "refresh_token"
CONF_INSTANCE_ID = "instance_id"

# Polling interval (seconds)
DEFAULT_SCAN_INTERVAL = 1800
# Retry native setup and route discovery while a native bulb is not working
NATIVE_RETRY_INTERVAL = timedelta(minutes=10)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SWITCH,
]
