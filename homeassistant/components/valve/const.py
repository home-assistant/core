"""Constants for the Valve entity platform."""

from enum import StrEnum

DOMAIN = "valve"


class ValveState(StrEnum):
    """State of Valve entities."""

    OPENING = "opening"
    CLOSING = "closing"
    CLOSED = "closed"
    OPEN = "open"
