"""Constants for the Moon integration."""
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "moon"
PLATFORMS: Final = [Platform.SENSOR, Platform.CALENDAR]

DEFAULT_NAME: Final = "Moon"

_LOGGER = logging.getLogger(__name__)

STATE_FIRST_QUARTER = "first_quarter"
STATE_FULL_MOON = "full_moon"
STATE_LAST_QUARTER = "last_quarter"
STATE_NEW_MOON = "new_moon"
STATE_WANING_CRESCENT = "waning_crescent"
STATE_WANING_GIBBOUS = "waning_gibbous"
STATE_WAXING_CRESCENT = "waxing_crescent"
STATE_WAXING_GIBBOUS = "waxing_gibbous"
