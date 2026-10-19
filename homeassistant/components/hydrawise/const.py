"""Constants for the Hydrawise integration."""

from datetime import timedelta
import logging

from homeassistant.const import __version__ as HA_VERSION

LOGGER = logging.getLogger(__package__)

APP_ID = f"homeassistant-{HA_VERSION}"

DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = timedelta(minutes=15)

MANUFACTURER = "Hydrawise"
MODEL_ZONE = "Zone"

MAIN_SCAN_INTERVAL = timedelta(minutes=5)
WATER_USE_SCAN_INTERVAL = timedelta(minutes=60)

# A controller picks up a command the next time it checks in with the cloud,
# which is usually every 15 seconds, but not always. After a command, refresh
# at this interval until the controller has checked in, for at most the timeout.
COMMAND_REFRESH_INTERVAL = timedelta(seconds=15)
COMMAND_REFRESH_TIMEOUT = timedelta(minutes=2)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"

SERVICE_RESUME = "resume"
SERVICE_START_WATERING = "start_watering"
SERVICE_SUSPEND = "suspend"

ATTR_DURATION = "duration"
ATTR_UNTIL = "until"
