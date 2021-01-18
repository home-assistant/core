"""Constants for the workday integration."""
from homeassistant.const import WEEKDAYS

DOMAIN = "workday"

OPTION_HOLIDAY = "holiday"

ALLOWED_DAYS = WEEKDAYS + [OPTION_HOLIDAY]

CONF_COUNTRY = "country"
CONF_SUBCOUNTRY = "subcountry"
CONF_ADVANCED = "advanced_conf"
CONF_PROVINCE = "province"
CONF_STATE = "state"
CONF_WORKDAYS = "workdays"
CONF_EXCLUDES = "excludes"
CONF_OFFSET = "days_offset"
CONF_ADD_HOLIDAYS = "add_holidays"
CONF_REMOVE_HOLIDAYS = "remove_holidays"

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ["sat", "sun", "holiday"]
DEFAULT_NAME = "Workday Sensor"
DEFAULT_OFFSET = 0

ERR_NO_COUNTRY = "no_country_err"
ERR_NO_SUBCOUNTRY = "no_subcountry_err"
