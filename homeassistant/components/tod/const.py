"""Constants for the Times of the Day integration."""

from enum import StrEnum

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET

DOMAIN = "tod"

CONF_AFTER_KIND = "after_kind"
CONF_AFTER_TIME = "after_time"
CONF_AFTER_OFFSET = "after_offset"
CONF_AFTER_OFFSET_MIN = "after_offset_min"
CONF_BEFORE_KIND = "before_kind"
CONF_BEFORE_TIME = "before_time"
CONF_BEFORE_OFFSET = "before_offset"
CONF_BEFORE_OFFSET_MIN = "before_offset_min"

KIND_FIXED = "fixed"


class TodKind(StrEnum):
    """Possible kinds of after/before values."""

    FIXED = KIND_FIXED
    SUNRISE = SUN_EVENT_SUNRISE
    SUNSET = SUN_EVENT_SUNSET
