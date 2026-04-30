"""Constants for the Moon integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "moon"
PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR]

DEFAULT_NAME: Final = "Moon"

STATE_FIRST_QUARTER: Final = "first_quarter"
STATE_FULL_MOON: Final = "full_moon"
STATE_LAST_QUARTER: Final = "last_quarter"
STATE_NEW_MOON: Final = "new_moon"
STATE_WANING_CRESCENT: Final = "waning_crescent"
STATE_WANING_GIBBOUS: Final = "waning_gibbous"
STATE_WAXING_CRESCENT: Final = "waxing_crescent"
STATE_WAXING_GIBBOUS: Final = "waxing_gibbous"

PHASE_OPTIONS: Final = [
    STATE_NEW_MOON,
    STATE_WAXING_CRESCENT,
    STATE_FIRST_QUARTER,
    STATE_WAXING_GIBBOUS,
    STATE_FULL_MOON,
    STATE_WANING_GIBBOUS,
    STATE_LAST_QUARTER,
    STATE_WANING_CRESCENT,
]
