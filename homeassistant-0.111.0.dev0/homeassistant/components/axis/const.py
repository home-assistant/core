"""Constants for the Axis component."""
import logging

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

LOGGER = logging.getLogger(__package__)

DOMAIN = "axis"

ATTR_MANUFACTURER = "Axis Communications AB"

CONF_CAMERA = "camera"
CONF_EVENTS = "events"
CONF_MODEL = "model"

DEFAULT_EVENTS = True
DEFAULT_TRIGGER_TIME = 0

PLATFORMS = [BINARY_SENSOR_DOMAIN, CAMERA_DOMAIN, SWITCH_DOMAIN]
