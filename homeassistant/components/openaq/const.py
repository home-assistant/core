"""Constants for the OpenAQ integration."""

from http.client import HTTPException
from json import JSONDecodeError
import logging
from typing import Final

from openaq import (
    ApiKeyMissingError,
    ForbiddenError,
    HTTPRateLimitError,
    NotAuthorizedError,
    RateLimitError,
)
from openaq.core.exceptions import APIError

from homeassistant.components.sensor import SensorDeviceClass

DOMAIN = "openaq"

LOGGER = logging.getLogger(__package__)

ATTRIBUTION: Final = "Data provided by OpenAQ"
CONF_LOCATION_ID: Final = "location_id"

MAX_RADIUS: Final = 25000
SUBENTRY_TYPE_LOCATION: Final = "location"

OPENAQ_AUTH_EXCEPTIONS: Final = (
    ApiKeyMissingError,
    ForbiddenError,
    NotAuthorizedError,
)
OPENAQ_RATE_LIMIT_EXCEPTIONS: Final = (HTTPRateLimitError, RateLimitError)
OPENAQ_API_EXCEPTIONS: Final = (
    APIError,
    OSError,
    HTTPException,
    JSONDecodeError,
)

PARAMETER_DEVICE_CLASSES: dict[str, SensorDeviceClass | None] = {
    "pm1": SensorDeviceClass.PM1,
    "pm25": SensorDeviceClass.PM25,
    "pm10": SensorDeviceClass.PM10,
    "co": SensorDeviceClass.CO,
    "co2": SensorDeviceClass.CO2,
    "no2": SensorDeviceClass.NITROGEN_DIOXIDE,
    "o3": SensorDeviceClass.OZONE,
    "so2": SensorDeviceClass.SULPHUR_DIOXIDE,
    "no": SensorDeviceClass.NITROGEN_MONOXIDE,
    "nox": None,
    "bc": None,
}
