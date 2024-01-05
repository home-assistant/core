"""Constants used by Teslemetry integration."""
from __future__ import annotations

from enum import IntEnum, StrEnum

DOMAIN = "teslemetry"

MODELS = {
    "model3": "Model 3",
    "modelx": "Model X",
    "modely": "Model Y",
    "models": "Model S",
}


class TeslemetryStatus(StrEnum):
    """Teslemetry status."""

    ASLEEP = "asleep"
    ONLINE = "online"


class TeslemetrySeatHeaterOptions(StrEnum):
    """Teslemetry seat heater options."""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TeslemetryClimateKeeper(StrEnum):
    """Teslemetry Climate Keeper Modes."""

    OFF = "off"
    ON = "on"
    DOG = "dog"
    CAMP = "camp"


class TeslemetryUpdateStatus(StrEnum):
    """Teslemetry Update Statuses."""

    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    WIFI_WAIT = "downloading_wifi_wait"
    SCHEDULED = "scheduled"


class TeslemetryCoverStates(IntEnum):
    """Teslemetry Cover states."""

    CLOSED = 0
    OPEN = 1
