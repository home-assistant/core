"""Constants for the Workday integration."""
from homeassistant.const import WEEKDAYS

DOMAIN = "workday"

ALLOWED_DAYS = WEEKDAYS + ["holiday"]

CONF_PROVINCE = "province"
CONF_WORKDAYS = "workdays"
CONF_EXCLUDES = "excludes"
CONF_OFFSET = "days_offset"
CONF_ADD_HOLIDAYS = "add_holidays"
CONF_REMOVE_HOLIDAYS = "remove_holidays"

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ["sat", "sun", "holiday"]
DEFAULT_OFFSET = 0
