"""Constants for the Aftership integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "aftership"

ATTRIBUTION: Final = "Information provided by AfterShip"
ATTR_TRACKINGS: Final = "trackings"

BASE: Final = "https://track.aftership.com/"

DEFAULT_NAME: Final = "aftership"
UPDATE_TOPIC: Final = f"{DOMAIN}_update"

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(minutes=15)
