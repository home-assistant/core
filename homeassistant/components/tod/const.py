"""Constants for the Times of the Day integration."""

from enum import StrEnum

DOMAIN = "tod"

CONF_AFTER_TIME = "after_time"
CONF_AFTER_OFFSET = "after_offset"
CONF_BEFORE_TIME = "before_time"
CONF_BEFORE_OFFSET = "before_offset"


class TodEntityStateAttribute(StrEnum):
    """State attributes for times of the day entities."""

    AFTER = "after"
    BEFORE = "before"
    NEXT_UPDATE = "next_update"
