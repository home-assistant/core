"""Constants for the NexBlue integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "nexblue"
CONF_REFRESH_TOKEN = "refresh_token"
DEFAULT_API_URL = "https://api.nexblue.com/third_party"
ACTIVE_CHARGING_STATES = frozenset(
    {
        2,  # Charging
        5,  # Waiting for available power
        7,  # Waiting for car response
    }
)
LOGGER = logging.getLogger(__package__)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
UPDATE_INTERVAL = timedelta(minutes=1)
