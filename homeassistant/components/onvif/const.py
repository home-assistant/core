"""Constants for the ONVIF component."""
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT,
    ATTR_ENTITY_ID)
import voluptuous as vol

DOMAIN = 'onvif'

DEFAULT_NAME = 'ONVIF Camera'
DEFAULT_PORT = 5000
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = '888888'
DEFAULT_ARGUMENTS = '-pred 1'
DEFAULT_PROFILE = 0

CONF_PROFILE = "profile"

ATTR_PAN = "pan"
ATTR_TILT = "tilt"
ATTR_ZOOM = "zoom"

DIR_UP = "UP"
DIR_DOWN = "DOWN"
DIR_LEFT = "LEFT"
DIR_RIGHT = "RIGHT"
ZOOM_OUT = "ZOOM_OUT"
ZOOM_IN = "ZOOM_IN"
PTZ_NONE = "NONE"

SERVICE_PTZ = "onvif_ptz"

ENTITIES = "entities"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_EXTRA_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
    vol.Optional(CONF_PROFILE, default=DEFAULT_PROFILE):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
})

SERVICE_PTZ_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_PAN: vol.In([DIR_LEFT, DIR_RIGHT, PTZ_NONE]),
    ATTR_TILT: vol.In([DIR_UP, DIR_DOWN, PTZ_NONE]),
    ATTR_ZOOM: vol.In([ZOOM_OUT, ZOOM_IN, PTZ_NONE])
})