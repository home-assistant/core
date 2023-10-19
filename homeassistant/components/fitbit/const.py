"""Constants for the Fitbit platform."""
from __future__ import annotations

from enum import StrEnum
from typing import Final

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

DOMAIN: Final = "fitbit"

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

BATTERY_LEVELS: Final[dict[str, int]] = {
    "High": 100,
    "Medium": 50,
    "Low": 20,
    "Empty": 0,
}


class FitbitUnitSystem(StrEnum):
    """Fitbit unit system set when sending requests to the Fitbit API.

    This is used as a header to tell the Fitbit API which type of units to return.
    https://dev.fitbit.com/build/reference/web-api/developer-guide/application-design/#Units

    Prefer to leave unset for newer configurations to use the Home Assistant default units.
    """

    LEGACY_DEFAULT = "default"
    """When set, will use an appropriate default using a legacy algorithm."""

    METRIC = "metric"
    """Use metric units."""

    EN_US = "en_US"
    """Use United States units."""

    EN_GB = "en_GB"
    """Use United Kingdom units."""


CONF_SCOPE: Final = "scope"


class FitbitScope(StrEnum):
    """OAuth scopes for fitbit."""

    ACTIVITY = "activity"
    HEART_RATE = "heartrate"
    NUTRITION = "nutrition"
    PROFILE = "profile"
    DEVICE = "settings"
    SLEEP = "sleep"
    WEIGHT = "weight"


OAUTH2_AUTHORIZE = "https://www.fitbit.com/oauth2/authorize"
OAUTH2_TOKEN = "https://api.fitbit.com/oauth2/token"
OAUTH_SCOPES = [scope.value for scope in FitbitScope]
