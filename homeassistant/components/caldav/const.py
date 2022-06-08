"""Constants for caldav integration."""
from caldav.lib.error import DAVError
from requests.exceptions import RequestException

CONF_ADD_CUSTO_CALENDAR = "add_new_custom_calendars"
CONF_CALENDAR = "calendar"
CONF_CALENDARS = "calendars"
CONF_CUSTOM_CALENDARS = "custom_calendars"
CONF_DAYS = "days"
CONF_SEARCH = "search"
DEFAULT_VERIFY_SSL = True
DOMAIN = "caldav"
OFFSET = "!!"
CALDAV_EXCEPTIONS = (RequestException, DAVError)
