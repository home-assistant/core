"""Constants for the NexBlue integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "nexblue"
CONF_REFRESH_TOKEN = "refresh_token"
DEFAULT_API_URL = "https://api.nexblue.com/third_party"
LOGGER = logging.getLogger(__package__)
PLATFORMS = [Platform.SENSOR]
UPDATE_INTERVAL = timedelta(minutes=1)
