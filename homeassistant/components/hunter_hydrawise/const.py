"""Constants for the Hunter Hydrawise integration."""
from datetime import timedelta
import logging

DOMAIN = "hunter_hydrawise"

LOGGER = logging.getLogger(__package__)

ALLOWED_WATERING_TIME = [5, 10, 15, 30, 45, 60]
CONF_WATERING_TIME = "watering_minutes"
ACCESS_TOKEN = "password"

DEFAULT_WATERING_TIME = 15

SCAN_INTERVAL = timedelta(seconds=120)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"
