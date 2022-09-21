"""Constants for the schedule integration."""
import logging
from typing import Final

DOMAIN: Final = "schedule"
LOGGER = logging.getLogger(__package__)

CONF_FRIDAY: Final = "friday"
CONF_FROM: Final = "from"
CONF_MONDAY: Final = "monday"
CONF_SATURDAY: Final = "saturday"
CONF_SUNDAY: Final = "sunday"
CONF_THURSDAY: Final = "thursday"
CONF_TO: Final = "to"
CONF_TUESDAY: Final = "tuesday"
CONF_WEDNESDAY: Final = "wednesday"
CONF_ALL_DAYS: Final = {
    CONF_MONDAY,
    CONF_TUESDAY,
    CONF_WEDNESDAY,
    CONF_THURSDAY,
    CONF_FRIDAY,
    CONF_SATURDAY,
    CONF_SUNDAY,
}

ATTR_NEXT_EVENT: Final = "next_event"

WEEKDAY_TO_CONF: Final = {
    0: CONF_MONDAY,
    1: CONF_TUESDAY,
    2: CONF_WEDNESDAY,
    3: CONF_THURSDAY,
    4: CONF_FRIDAY,
    5: CONF_SATURDAY,
    6: CONF_SUNDAY,
}
