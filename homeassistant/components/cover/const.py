"""Constants for cover entity platform."""

from enum import IntFlag, StrEnum

DOMAIN = "cover"

ATTR_CURRENT_POSITION = "current_position"
ATTR_CURRENT_TILT_POSITION = "current_tilt_position"
ATTR_IS_CLOSED = "is_closed"
ATTR_POSITION = "position"
ATTR_TILT_POSITION = "tilt_position"

INTENT_OPEN_COVER = "HassOpenCover"
INTENT_CLOSE_COVER = "HassCloseCover"


class CoverEntityFeature(IntFlag):
    """Supported features of the cover entity."""

    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8
    OPEN_TILT = 16
    CLOSE_TILT = 32
    STOP_TILT = 64
    SET_TILT_POSITION = 128


class CoverState(StrEnum):
    """State of Cover entities."""

    CLOSED = "closed"
    CLOSING = "closing"
    OPEN = "open"
    OPENING = "opening"


class CoverDeviceClass(StrEnum):
    """Device class for cover."""

    # Refer to the cover dev docs for device class descriptions
    AWNING = "awning"
    BLIND = "blind"
    CURTAIN = "curtain"
    DAMPER = "damper"
    DOOR = "door"
    GARAGE = "garage"
    GATE = "gate"
    SHADE = "shade"
    SHUTTER = "shutter"
    WINDOW = "window"
