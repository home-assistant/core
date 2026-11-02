"""Constants for the Aftership integration."""

from datetime import timedelta
from enum import StrEnum
from typing import Final

import probatio

from homeassistant.helpers import config_validation as cv

DOMAIN: Final = "aftership"

ATTRIBUTION: Final = "Information provided by AfterShip"
ATTR_TRACKINGS: Final = "trackings"

BASE: Final = "https://track.aftership.com/"

DEFAULT_NAME: Final = "aftership"
UPDATE_TOPIC: Final = f"{DOMAIN}_update"

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(minutes=15)


class AfterShipService(StrEnum):
    """Store keys for AfterShip services."""

    ADD_TRACKING = "add_tracking"
    REMOVE_TRACKING = "remove_tracking"


class AfterShipServiceArgument(StrEnum):
    """Store keys for AfterShip service arguments."""

    TRACKING_NUMBER = "tracking_number"
    TITLE = "title"
    SLUG = "slug"


ADD_TRACKING_SERVICE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(AfterShipServiceArgument.TRACKING_NUMBER): cv.string,
        probatio.Optional(AfterShipServiceArgument.TITLE): cv.string,
        probatio.Optional(AfterShipServiceArgument.SLUG): cv.string,
    }
)

REMOVE_TRACKING_SERVICE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(AfterShipServiceArgument.SLUG): cv.string,
        probatio.Required(AfterShipServiceArgument.TRACKING_NUMBER): cv.string,
    }
)
