"""Constants used by Tessie integration."""
from __future__ import annotations

from enum import IntEnum, StrEnum

DOMAIN = "tessie"

MODELS = {
    "model3": "Model 3",
    "modelx": "Model X",
    "modely": "Model Y",
    "models": "Model S",
}


class TessieStatus(StrEnum):
    """Tessie status."""

    ASLEEP = "asleep"
    ONLINE = "online"


class TessieSeatHeaterOptions(StrEnum):
    """Tessie seat heater options."""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TessieClimateKeeper(StrEnum):
    """Tessie Climate Keeper Modes."""

    OFF = "off"
    ON = "on"
    DOG = "dog"
    CAMP = "camp"


class TessieUpdateStatus(StrEnum):
    """Tessie Update Statuses."""

    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    WIFI_WAIT = "downloading_wifi_wait"
    SCHEDULED = "scheduled"


class TessieCoverStates(IntEnum):
    """Tessie Cover states."""

    CLOSED = 0
    OPEN = 1
