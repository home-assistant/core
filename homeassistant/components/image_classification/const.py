"""Constants for the Image classification integration."""

from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON

DOMAIN = "image_classification"
LOGGER = logging.getLogger(__package__)

CONF_AI_TASK_ENTITY_ID = "ai_task_entity_id"
CONF_LEFT = "left"
CONF_TOP = "top"
CONF_RIGHT = "right"
CONF_BOTTOM = "bottom"
CONF_FRAMES = "frames"

DEFAULT_REGION = {CONF_LEFT: 0, CONF_TOP: 0, CONF_RIGHT: 100, CONF_BOTTOM: 100}

# States a camera can show for an area; the rest need a measurement.
DEVICE_CLASSES = [
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.GARAGE_DOOR,
    BinarySensorDeviceClass.OCCUPANCY,
    BinarySensorDeviceClass.OPENING,
    BinarySensorDeviceClass.WINDOW,
]

DEFAULT_DEVICE_CLASS = BinarySensorDeviceClass.OCCUPANCY
STATES = (STATE_ON, STATE_OFF)

# The probability a state needs; below it the sensor is unknown.
THRESHOLD = 0.8

# Integration that classifies on this device, the default when no AI Task
# entity is preferred for image classification.
LOCAL_VISION_DOMAIN = "local_vision"

UPDATE_INTERVAL = timedelta(minutes=5)
