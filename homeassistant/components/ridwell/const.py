"""Constants for the Ridwell integration."""

import logging

DOMAIN = "ridwell"

LOGGER = logging.getLogger(__package__)

SENSOR_TYPE_NEXT_PICKUP = "next_pickup"

CONF_CALENDAR_TITLE = "conf_calendar_title"

CALENDAR_TITLE_STATUS = "pickup_status"
CALENDAR_TITLE_ROTATING = "rotating_category"
CALENDAR_TITLE_NONE = "no_detail"

CALENDAR_TITLE_OPTIONS = [
    CALENDAR_TITLE_STATUS,
    CALENDAR_TITLE_ROTATING,
    CALENDAR_TITLE_NONE,
]
