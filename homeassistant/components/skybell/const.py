"""Constants for the Skybell HD Doorbell."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
)
from homeassistant.const import __version__

DATA_COORDINATOR = "coordinator"
DATA_DEVICES = "devices"

DOMAIN = "skybell"
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

BINARY_SENSOR_TYPES = {
    "button": ["Button", DEVICE_CLASS_OCCUPANCY, "device:sensor:button"],
    "motion": ["Motion", DEVICE_CLASS_MOTION, "device:sensor:motion"],
}

CAMERA_TYPES = {"activity": "Last Activity", "avatar": None}

SWITCH_TYPES = {"do_not_disturb": "Do Not Disturb", "motion_sensor": "Motion Sensor"}

SENSOR_TYPES = {"chime_level": ["Chime Level", "mdi:bell-ring"]}
