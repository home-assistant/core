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


class TessieSeatCoolerOptions(StrEnum):
    """Tessie seat cooler options."""

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


class TessieWallConnectorStates(IntEnum):
    """Tessie Wall Connector states."""

    BOOTING = 0
    CHARGING = 1
    DISCONNECTED = 2
    CONNECTED = 4
    SCHEDULED = 5
    NEGOTIATING = 6
    ERROR = 7
    CHARGING_FINISHED = 8
    WAITING_CAR = 9
    CHARGING_REDUCED = 10
