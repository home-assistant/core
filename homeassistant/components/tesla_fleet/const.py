"""Constants used by Tesla Fleet integration."""

from __future__ import annotations

from enum import StrEnum
import logging

from tesla_fleet_api.const import Scope

DOMAIN = "tesla_fleet"

CONF_REFRESH_TOKEN = "refresh_token"

LOGGER = logging.getLogger(__package__)

CLIENT_ID = "71b813eb-4a2e-483a-b831-4dec5cb9bf0d"
AUTHORIZE_URL = "https://auth.tesla.com/oauth2/v3/authorize"
TOKEN_URL = "https://auth.tesla.com/oauth2/v3/token"

SCOPES = [
    Scope.OPENID,
    Scope.OFFLINE_ACCESS,
    Scope.VEHICLE_DEVICE_DATA,
    Scope.VEHICLE_LOCATION,
    Scope.VEHICLE_CMDS,
    Scope.VEHICLE_CHARGING_CMDS,
    Scope.ENERGY_DEVICE_DATA,
    Scope.ENERGY_CMDS,
]

MODELS = {
    "S": "Model S",
    "3": "Model 3",
    "X": "Model X",
    "Y": "Model Y",
    "C": "Cybertruck",
    "T": "Tesla Semi",
}


class TeslaFleetState(StrEnum):
    """Teslemetry Vehicle States."""

    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"


class TeslaFleetClimateSide(StrEnum):
    """Tesla Fleet Climate Keeper Modes."""

    DRIVER = "driver_temp"
    PASSENGER = "passenger_temp"
