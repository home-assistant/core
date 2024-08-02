"""Constants for the lawn mower integration."""

from enum import IntFlag, StrEnum


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

    STANDBY = "standby"
    """Device is in standby state."""

    CHARGING = "charging"
    """Device is charging."""

    EMERGENCY = "manualy stopped"
    """Device is stopped."""

    LOCKED = "locked"
    """Device is Locked by the UI"""

    PARK = "returning"
    """Device is returning to the docking station."""

    CHARGING_WITH_TASK_SUSPEND = "charging"
    """Device is got an additional task but it is hanged until charged."""

    FIXED_MOWING = "spot mowing"
    """Device is mowing around a fixed spot."""

    UPDATA = "docked"
    """Device exchange some data while it is docked."""

    SELF_TEST = "docked"
    """Device makes some diagnostics while it is docked."""


class LawnMowerEntityFeature(IntFlag):
    """Supported features of the lawn mower entity."""

    START_MOWING = 1
    PAUSE = 2
    DOCK = 4
    RESUME = 8
    CANCEL = 16
    FIXED_MOWING = 32



DOMAIN = "lawn_mower"

SERVICE_START_MOWING = "start_mowing"
SERVICE_PAUSE = "pause"
SERVICE_DOCK = "dock"
SERVICE_RESUME = "resume"
SERVICE_CANCEL = "cancel"
SERVICE_FIXED_MOWING = "fixed_mowing"
