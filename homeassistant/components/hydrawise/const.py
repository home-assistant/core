"""Constants for the Hydrawise integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = timedelta(minutes=15)

MANUFACTURER = "Hydrawise"

SCAN_INTERVAL = timedelta(seconds=60)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"

SERVICE_RESUME = "resume"
SERVICE_START_WATERING = "start_watering"
SERVICE_SUSPEND = "suspend"

ATTR_DURATION = "duration"
ATTR_UNTIL = "until"
