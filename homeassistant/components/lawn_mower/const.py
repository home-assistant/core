"""Constants for the lawn mower integration."""

from enum import IntFlag, StrEnum
from typing import Final


class LawnMowerActivity(StrEnum):
    """Activity state of lawn mower devices."""

    ERROR = "error"
    """Device is in error state, needs assistance."""

    PAUSED = "paused"
    """Paused during activity."""

    MOWING = "mowing"
    """Device is mowing."""

    DOCKED = "docked"
    """Device is docked."""

    RETURNING = "returning"
    """Device is returning."""

    IDLE = "idle"
    """Device is stopped, but neither docked nor paused."""


class LawnMowerEntityFeature(IntFlag):
    """Supported features of the lawn mower entity."""

    START_MOWING = 1
    PAUSE = 2
    DOCK = 4
    STOP = 8


DOMAIN: Final = "lawn_mower"

SERVICE_START_MOWING = "start_mowing"
SERVICE_PAUSE = "pause"
SERVICE_DOCK = "dock"
SERVICE_STOP = "stop"
