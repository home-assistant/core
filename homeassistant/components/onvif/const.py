"""Constants for the onvif component."""

import asyncio
from collections.abc import Mapping
from enum import Enum
import logging
from typing import Literal

import aiohttp
from onvif.exceptions import ONVIFError
from zeep.exceptions import Fault, TransportError

LOGGER = logging.getLogger(__package__)

DOMAIN = "onvif"

DEFAULT_PORT = 80
DEFAULT_ARGUMENTS = "-pred 1"

CONF_DEVICE_ID = "deviceid"
CONF_HARDWARE = "hardware"
CONF_SNAPSHOT_AUTH = "snapshot_auth"
CONF_ENABLE_WEBHOOKS = "enable_webhooks"
DEFAULT_ENABLE_WEBHOOKS = True

ATTR_PAN = "pan"
ATTR_TILT = "tilt"
ATTR_ZOOM = "zoom"
ATTR_DISTANCE = "distance"
ATTR_SPEED = "speed"
ATTR_MOVE_MODE = "move_mode"
ATTR_CONTINUOUS_DURATION = "continuous_duration"
ATTR_PRESET = "preset"


SERVICE_PTZ = "ptz"


# Some cameras don't support the GetServiceCapabilities call
# and will return a 404 error which is caught by TransportError
GET_CAPABILITIES_EXCEPTIONS = (
    ONVIFError,
    Fault,
    aiohttp.ClientError,
    asyncio.TimeoutError,
    TransportError,
)

# Literals
MoveMode = Literal[
    "AbsoluteMove", "ContinuousMove", "GotoPreset", "RelativeMove", "Stop"
]

ABSOLUTE_MOVE: MoveMode = "AbsoluteMove"
CONTINUOUS_MOVE: MoveMode = "ContinuousMove"
GOTOPRESET_MOVE: MoveMode = "GotoPreset"
RELATIVE_MOVE: MoveMode = "RelativeMove"
STOP_MOVE: MoveMode = "Stop"


class MoveModeRequirement(str, Enum):
    """Per-mode validation flags used by the service layer."""

    AXES = "axes"
    SPEED = "speed"
    CONTINUOUS_DURATION = "duration"
    DISTANCE = "distance"
    PRESETS = "presets"


MODE_REQUIREMENTS: dict[MoveMode, set[MoveModeRequirement]] = {
    CONTINUOUS_MOVE: {
        MoveModeRequirement.AXES,
        MoveModeRequirement.SPEED,
        MoveModeRequirement.CONTINUOUS_DURATION,
    },
    RELATIVE_MOVE: {MoveModeRequirement.AXES, MoveModeRequirement.DISTANCE},
    ABSOLUTE_MOVE: {MoveModeRequirement.AXES},
    GOTOPRESET_MOVE: {MoveModeRequirement.PRESETS},
    STOP_MOVE: set(),
}

PanDir = Literal["LEFT", "RIGHT"]
TiltDir = Literal["UP", "DOWN"]
ZoomDir = Literal["ZOOM_IN", "ZOOM_OUT"]

DIR_LEFT: PanDir = "LEFT"
DIR_RIGHT: PanDir = "RIGHT"
DIR_UP: TiltDir = "UP"
DIR_DOWN: TiltDir = "DOWN"
ZOOM_IN: ZoomDir = "ZOOM_IN"
ZOOM_OUT: ZoomDir = "ZOOM_OUT"

PAN_FACTOR: Mapping[str, float] = {DIR_RIGHT: 1.0, DIR_LEFT: -1.0}
TILT_FACTOR: Mapping[str, float] = {DIR_UP: 1.0, DIR_DOWN: -1.0}
ZOOM_FACTOR: Mapping[str, float] = {ZOOM_IN: 1.0, ZOOM_OUT: -1.0}
