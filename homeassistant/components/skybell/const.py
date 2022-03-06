"""Constants for the Skybell HD Doorbell."""
import logging
from typing import Final

ATTRIBUTION = "Data provided by Skybell.com"

DEFAULT_CACHEDB = "./skybell_cache.pickle"
DEFAULT_NAME = "SkyBell"
DOMAIN: Final = "skybell"

IMAGE_AVATAR = "avatar"
IMAGE_ACTIVITY = "activity"

LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "skybell_notification"
NOTIFICATION_TITLE = "Skybell Sensor Setup"
