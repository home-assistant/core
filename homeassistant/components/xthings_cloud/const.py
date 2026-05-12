"""Constants for Xthings Cloud integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "xthings_cloud"
LOGGER = logging.getLogger(__package__)

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_CLIENT_ID = "client_id"
CONF_INSTANCE_ID = "instance_id"

# Polling interval (seconds)
DEFAULT_SCAN_INTERVAL = 1800

PLATFORMS: list[Platform] = [Platform.LIGHT]
