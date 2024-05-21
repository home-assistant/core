"""Constants for the Hydrawise integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

ALLOWED_WATERING_TIME = [5, 10, 15, 30, 45, 60]
CONF_WATERING_TIME = "watering_minutes"

DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = timedelta(minutes=15)

MANUFACTURER = "Hydrawise"

SCAN_INTERVAL = timedelta(seconds=30)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"
