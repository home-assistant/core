"""Constants for the Atomberg integration."""

from datetime import timedelta
import logging

DOMAIN = "atomberg"
LOGGER = logging.getLogger(__package__)

CONF_REFRESH_TOKEN = "refresh_token"
CONF_DEVICE_IDS = "device_ids"

# The public API allows 100 calls per day; 48 polls leaves room for commands.
UPDATE_INTERVAL = timedelta(minutes=30)

FAN_SPEEDS = [1, 2, 3, 4, 5, 6]
