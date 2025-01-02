"""Constants for the Hydrawise integration."""

from datetime import timedelta
import logging

from homeassistant.const import __version__ as HA_VERSION

LOGGER = logging.getLogger(__package__)

APP_ID = f"homeassistant-{HA_VERSION}"

DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = timedelta(minutes=15)

MANUFACTURER = "Hydrawise"

MAIN_SCAN_INTERVAL = timedelta(minutes=5)
WATER_USE_SCAN_INTERVAL = timedelta(minutes=60)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"

SERVICE_RESUME = "resume"
SERVICE_START_WATERING = "start_watering"
SERVICE_SUSPEND = "suspend"

ATTR_DURATION = "duration"
ATTR_UNTIL = "until"
