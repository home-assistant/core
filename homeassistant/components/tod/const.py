"""Constants for the Times of the Day integration."""

from datetime import timedelta

DOMAIN = "tod"

CONF_AFTER_TIME = "after_time"
CONF_AFTER_OFFSET = "after_offset"
CONF_BEFORE_TIME = "before_time"
CONF_BEFORE_OFFSET = "before_offset"

MAX_OFFSET = timedelta(days=1) - timedelta(microseconds=1)
