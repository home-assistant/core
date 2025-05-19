"""Constants for the Paperless-ngx integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "paperless_ngx"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

REMOTE_VERSION_UPDATE_INTERVAL_HOURS = 24
