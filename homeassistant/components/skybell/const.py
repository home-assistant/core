"""Constants for the Skybell HD Doorbell."""
import logging
from typing import Final

CONF_ACTIVITY_NAME = "activity_name"
CONF_AVATAR_NAME = "avatar_name"
DEFAULT_CACHEDB = "./skybell_cache.pickle"
DEFAULT_NAME = "SkyBell"
DOMAIN: Final = "skybell"

IMAGE_AVATAR = "avatar"
IMAGE_ACTIVITY = "activity"

LOGGER = logging.getLogger(__package__)
