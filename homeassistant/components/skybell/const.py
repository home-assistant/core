"""Constants for the Skybell HD Doorbell."""
from datetime import timedelta
from typing import Final

DATA_COORDINATOR = "coordinator"
DATA_DEVICES = "devices"

DOMAIN: Final = "skybell"
DEFAULT_NAME = "SkyBell"

ATTRIBUTION = "Data provided by Skybell.com"

NOTIFICATION_ID = "skybell_notification"
NOTIFICATION_TITLE = "Skybell Sensor Setup"

DEFAULT_CACHEDB = "./skybell_cache.pickle"

IMAGE_AVATAR = "avatar"
IMAGE_ACTIVITY = "activity"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
