"""Constants used by Teslemetry integration."""

from __future__ import annotations

from enum import StrEnum
import logging

DOMAIN = "teslemetry"

LOGGER = logging.getLogger(__package__)

MODELS = {
    "S": "Model S",
    "3": "Model 3",
    "X": "Model X",
    "Y": "Model Y",
}

ENERGY_HISTORY_FIELDS = [
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
]


class TeslemetryState(StrEnum):
    """Teslemetry Vehicle States."""

    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"


class TeslemetryClimateSide(StrEnum):
    """Teslemetry Climate Keeper Modes."""

    DRIVER = "driver_temp"
    PASSENGER = "passenger_temp"


class TeslemetryEnum:
    """Helper class to handle options for protobuf enums."""

    def __init__(self, prefix: str, options: list[str]):
        """Create a new options list."""
        self.prefix = prefix.lower()
        self.options = [option.lower() for option in options]

    def get(self, value, default: str | None = None) -> str | None:
        """Get the value if it is a valid option."""
        if isinstance(value, str):
            option = value.lower().replace(self.prefix, "")
            if option in self.options:
                return option
        return default


WindowState = TeslemetryEnum("WindowState", ["opened", "partiallyopen", "closed"])
