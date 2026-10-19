"""Constants for the Local vision integration."""

from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON

DOMAIN = "local_vision"
LOGGER = logging.getLogger(__package__)

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

UPDATE_INTERVAL = timedelta(minutes=5)
