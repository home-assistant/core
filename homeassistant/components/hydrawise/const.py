"""Constants for the Hydrawise integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = timedelta(minutes=15)
# The API allows specifying a watering time larger than 90 minutes, but doing
# so does not behave as expected. Likewise, the Hydrawise app has a maximum
# allowed value of 90 minutes. So we stick with that.
MAX_WATERING_TIME = timedelta(minutes=90)

MANUFACTURER = "Hydrawise"

SCAN_INTERVAL = timedelta(seconds=30)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"

SERVICE_RESUME = "resume"
SERVICE_START_WATERING = "start_watering"
SERVICE_SUSPEND = "suspend"

ATTR_DURATION = "duration"
ATTR_UNTIL = "until"
