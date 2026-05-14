"""Constants for the Valve entity platform."""

from enum import IntFlag, StrEnum

DOMAIN = "valve"


class ValveDeviceClass(StrEnum):
    """Device class for valve."""

    # Refer to the valve dev docs for device class descriptions
    WATER = "water"
    GAS = "gas"


class ValveEntityFeature(IntFlag):
    """Supported features of the valve entity."""

    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8


class ValveState(StrEnum):
    """State of Valve entities."""

    OPENING = "opening"
    CLOSING = "closing"
    CLOSED = "closed"
    OPEN = "open"
