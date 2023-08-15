"""Constants for the lawn mower integration."""
from enum import IntFlag, StrEnum


class LawnMowerActivity(StrEnum):
    """Activity state of lawn mower devices."""

    # Device is in error state, needs assistance
    ERROR = "error"

    # Paused during activity
    PAUSED = "paused"

    # Device is mowing
    MOWING = "mowing"

    # Device is docked
    DOCKED = "docked"


class LawnMowerEntityFeature(IntFlag):
    """Supported features of the lawn mower entity."""

    START_MOWING = 1
    PAUSE = 2
    DOCK = 4


DOMAIN = "lawn_mower"

SERVICE_START_MOWING = "start_mowing"
SERVICE_PAUSE = "pause"
SERVICE_DOCK = "dock"
