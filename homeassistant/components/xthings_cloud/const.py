"""Constants for Xthings Cloud integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "xthings_cloud"
LOGGER = logging.getLogger(__package__)

# pylint: disable-next=home-assistant-duplicate-const
CONF_EMAIL = "email"
# pylint: disable-next=home-assistant-duplicate-const
CONF_PASSWORD = "password"
# pylint: disable-next=home-assistant-duplicate-const
CONF_TOKEN = "token"
CONF_REFRESH_TOKEN = "refresh_token"
# pylint: disable-next=home-assistant-duplicate-const
CONF_CLIENT_ID = "client_id"
CONF_INSTANCE_ID = "instance_id"

# Polling interval (seconds)
DEFAULT_SCAN_INTERVAL = 1800

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH]
