"""Constants for the Skybell HD Doorbell."""
from datetime import timedelta
from typing import Final

from homeassistant.const import __version__

DATA_COORDINATOR = "coordinator"
DATA_DEVICES = "devices"

DOMAIN: Final = "skybell"
DEFAULT_NAME = "SkyBell"

ATTRIBUTION = "Data provided by Skybell.com"

NOTIFICATION_ID = "skybell_notification"
NOTIFICATION_TITLE = "Skybell Sensor Setup"

DEFAULT_CACHEDB = "./skybell_cache.pickle"

AGENT_IDENTIFIER = f"HomeAssistant/{__version__}"

IMAGE_AVATAR = "avatar"
IMAGE_ACTIVITY = "activity"

CONF_ACTIVITY_NAME = "activity_name"
CONF_AVATAR_NAME = "avatar_name"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CAMERA_TYPES = {"activity": "Last Activity", "avatar": None}
