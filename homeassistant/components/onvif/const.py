"""Constants for the onvif component."""
import logging

from httpx import RequestError
from onvif.exceptions import ONVIFError
from zeep.exceptions import Fault, TransportError

LOGGER = logging.getLogger(__package__)

DOMAIN = "onvif"

DEFAULT_PORT = 80
DEFAULT_ARGUMENTS = "-pred 1"

CONF_DEVICE_ID = "deviceid"
CONF_SNAPSHOT_AUTH = "snapshot_auth"

ATTR_PAN = "pan"
ATTR_TILT = "tilt"
ATTR_ZOOM = "zoom"
ATTR_DISTANCE = "distance"
ATTR_SPEED = "speed"
ATTR_MOVE_MODE = "move_mode"
ATTR_CONTINUOUS_DURATION = "continuous_duration"
ATTR_PRESET = "preset"

DIR_UP = "UP"
DIR_DOWN = "DOWN"
DIR_LEFT = "LEFT"
DIR_RIGHT = "RIGHT"
ZOOM_OUT = "ZOOM_OUT"
ZOOM_IN = "ZOOM_IN"
PAN_FACTOR = {DIR_RIGHT: 1, DIR_LEFT: -1}
TILT_FACTOR = {DIR_UP: 1, DIR_DOWN: -1}
ZOOM_FACTOR = {ZOOM_IN: 1, ZOOM_OUT: -1}
CONTINUOUS_MOVE = "ContinuousMove"
RELATIVE_MOVE = "RelativeMove"
ABSOLUTE_MOVE = "AbsoluteMove"
GOTOPRESET_MOVE = "GotoPreset"
STOP_MOVE = "Stop"

SERVICE_PTZ = "ptz"


# Some cameras don't support the GetServiceCapabilities call
# and will return a 404 error which is caught by TransportError
GET_CAPABILITIES_EXCEPTIONS = (ONVIFError, Fault, RequestError, TransportError)
