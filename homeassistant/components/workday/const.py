"""Add constants for Workday integration."""

import logging

from homeassistant.const import WEEKDAYS, Platform

LOGGER = logging.getLogger(__package__)

ALLOWED_DAYS = [*WEEKDAYS, "holiday"]

DOMAIN = "workday"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR]

CONF_PROVINCE = "province"
CONF_WORKDAYS = "workdays"
CONF_EXCLUDES = "excludes"
CONF_OFFSET = "days_offset"
CONF_ADD_HOLIDAYS = "add_holidays"
CONF_REMOVE_HOLIDAYS = "remove_holidays"
CONF_REMOVE_HOLIDAYS_NAMED = "remove_holidays_named"
CONF_CATEGORY = "category"
CONF_START_DATE = "start_date"
CONF_END_DATE = "end_date"

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ["sat", "sun", "holiday"]
DEFAULT_NAME = "Workday Sensor"
DEFAULT_OFFSET = 0
