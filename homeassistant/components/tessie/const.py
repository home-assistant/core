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


class TessieState(StrEnum):
    """Tessie status."""

    ASLEEP = "asleep"
    ONLINE = "online"


class TessieStatus(StrEnum):
    """Tessie status."""

    ASLEEP = "asleep"
    AWAKE = "awake"
    WAITING = "waiting_for_sleep"


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


class TessieChargeCableLockStates(StrEnum):
    """Tessie Charge Cable Lock states."""

    ENGAGED = "Engaged"
    DISENGAGED = "Disengaged"


TessieChargeStates = {
    "Starting": "starting",
    "Charging": "charging",
    "Stopped": "stopped",
    "Complete": "complete",
    "Disconnected": "disconnected",
    "NoPower": "no_power",
}

TessieWallConnectorStates = {
    0: "booting",
    1: "charging",
    2: "disconnected",
    4: "connected",
    5: "scheduled",
    6: "negotiating",
    7: "error",
    8: "charging_finished",
    9: "waiting_car",
    10: "charging_reduced",
}
