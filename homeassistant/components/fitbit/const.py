"""Constants for the Fitbit platform."""
from __future__ import annotations

from typing import Final

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    UnitOfLength,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)

ATTR_ACCESS_TOKEN: Final = "access_token"
ATTR_REFRESH_TOKEN: Final = "refresh_token"
ATTR_LAST_SAVED_AT: Final = "last_saved_at"

ATTR_DURATION: Final = "duration"
ATTR_DISTANCE: Final = "distance"
ATTR_ELEVATION: Final = "elevation"
ATTR_HEIGHT: Final = "height"
ATTR_WEIGHT: Final = "weight"
ATTR_BODY: Final = "body"
ATTR_LIQUIDS: Final = "liquids"
ATTR_BLOOD_GLUCOSE: Final = "blood glucose"
ATTR_BATTERY: Final = "battery"

CONF_MONITORED_RESOURCES: Final = "monitored_resources"
CONF_CLOCK_FORMAT: Final = "clock_format"
ATTRIBUTION: Final = "Data provided by Fitbit.com"

FITBIT_AUTH_CALLBACK_PATH: Final = "/api/fitbit/callback"
FITBIT_AUTH_START: Final = "/api/fitbit"
FITBIT_CONFIG_FILE: Final = "fitbit.conf"
FITBIT_DEFAULT_RESOURCES: Final[list[str]] = ["activities/steps"]

DEFAULT_CONFIG: Final[dict[str, str]] = {
    CONF_CLIENT_ID: "CLIENT_ID_HERE",
    CONF_CLIENT_SECRET: "CLIENT_SECRET_HERE",
}
DEFAULT_CLOCK_FORMAT: Final = "24H"


FITBIT_MEASUREMENTS: Final[dict[str, dict[str, str]]] = {
    "en_US": {
        ATTR_DURATION: UnitOfTime.MILLISECONDS,
        ATTR_DISTANCE: UnitOfLength.MILES,
        ATTR_ELEVATION: UnitOfLength.FEET,
        ATTR_HEIGHT: UnitOfLength.INCHES,
        ATTR_WEIGHT: UnitOfMass.POUNDS,
        ATTR_BODY: UnitOfLength.INCHES,
        ATTR_LIQUIDS: UnitOfVolume.FLUID_OUNCES,
        ATTR_BLOOD_GLUCOSE: f"{UnitOfMass.MILLIGRAMS}/dL",
        ATTR_BATTERY: "",
    },
    "en_GB": {
        ATTR_DURATION: UnitOfTime.MILLISECONDS,
        ATTR_DISTANCE: UnitOfLength.KILOMETERS,
        ATTR_ELEVATION: UnitOfLength.METERS,
        ATTR_HEIGHT: UnitOfLength.CENTIMETERS,
        ATTR_WEIGHT: UnitOfMass.STONES,
        ATTR_BODY: UnitOfLength.CENTIMETERS,
        ATTR_LIQUIDS: UnitOfVolume.MILLILITERS,
        ATTR_BLOOD_GLUCOSE: "mmol/L",
        ATTR_BATTERY: "",
    },
    "metric": {
        ATTR_DURATION: UnitOfTime.MILLISECONDS,
        ATTR_DISTANCE: UnitOfLength.KILOMETERS,
        ATTR_ELEVATION: UnitOfLength.METERS,
        ATTR_HEIGHT: UnitOfLength.CENTIMETERS,
        ATTR_WEIGHT: UnitOfMass.KILOGRAMS,
        ATTR_BODY: UnitOfLength.CENTIMETERS,
        ATTR_LIQUIDS: UnitOfVolume.MILLILITERS,
        ATTR_BLOOD_GLUCOSE: "mmol/L",
        ATTR_BATTERY: "",
    },
}

BATTERY_LEVELS: Final[dict[str, int]] = {
    "High": 100,
    "Medium": 50,
    "Low": 20,
    "Empty": 0,
}
