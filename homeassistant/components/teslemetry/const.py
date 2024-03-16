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


class TeslemetryTimestamp(StrEnum):
    """Teslemetry Timestamps."""

    VEHICLE_STATE = "vehicle_state_timestamp"
    DRIVE_STATE = "drive_state_timestamp"
    CHARGE_STATE = "charge_state_timestamp"
    CLIMATE_STATE = "climate_state_timestamp"
    GUI_SETTINGS = "gui_settings_timestamp"
    VEHICLE_CONFIG = "vehicle_config_timestamp"


class TeslemetryState(StrEnum):
    """Teslemetry Vehicle States."""

    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"


class TeslemetryClimateSide(StrEnum):
    """Teslemetry Climate Keeper Modes."""

    DRIVER = "driver_temp"
    PASSENGER = "passenger_temp"
