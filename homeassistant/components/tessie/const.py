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

TRANSLATED_ERRORS = {
    "unknown": "unknown",
    "not supported": "not_supported",
    "cable connected": "cable_connected",
    "already active": "already_active",
    "already inactive": "already_inactive",
    "incorrect pin": "incorrect_pin",
    "no cable": "no_cable",
    "cpd_enabled": "cpd_enabled",
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

TessieChargePortLatchStates = {
    "Engaged": "engaged",
    "Disengaged": "disengaged",
    "Blocking": "blocking",
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


ENERGY_HISTORY_FIELDS = (
    "solar_energy_exported",
    "generator_energy_exported",
    "grid_energy_imported",
    "grid_services_energy_imported",
    "grid_services_energy_exported",
    "grid_energy_exported_from_solar",
    "grid_energy_exported_from_generator",
    "grid_energy_exported_from_battery",
    "battery_energy_exported",
    "battery_energy_imported_from_grid",
    "battery_energy_imported_from_solar",
    "battery_energy_imported_from_generator",
    "consumer_energy_imported_from_grid",
    "consumer_energy_imported_from_solar",
    "consumer_energy_imported_from_battery",
    "consumer_energy_imported_from_generator",
    "total_home_usage",
    "total_battery_charge",
    "total_battery_discharge",
    "total_solar_generation",
    "total_grid_energy_exported",
)
