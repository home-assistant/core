"""Constants for the lawn mower integration."""
from enum import IntFlag, StrEnum


class LawnMowerActivity(StrEnum):
    """Activity state of lawn mower devices."""

    # Device is in error state, needs assistance
    ERROR = "error"

    # Paused during mow
    PAUSED = "paused"

    # Device is mowing
    MOWING = "mowing"

    # Device is in process of going back to dock
    DOCKING = "docking"

    # Device is docked and schedule is enabled to auto mow
    DOCKED_SCHEDULE_DISABLED = "docked_schedule_disabled"

    # Device is docked and schedule is disabled, mowing is manually done
    DOCKED_SCHEDULE_ENABLED = "docked_schedule_enabled"


class LawnMowerEntityFeature(IntFlag):
    """Supported features of the lawn mower entity."""

    START_MOWING = 1
    PAUSE = 2
    DOCK = 4
    ENABLE_SCHEDULE = 8
    DISABLE_SCHEDULE = 16


DOMAIN = "lawn_mower"

SERVICE_START_MOWING = "start_mowing"
SERVICE_PAUSE = "pause"
SERVICE_ENABLE_SCHEDULE = "enable_schedule"
SERVICE_DISABLE_SCHEDULE = "disable_schedule"
SERVICE_DOCK = "dock"
