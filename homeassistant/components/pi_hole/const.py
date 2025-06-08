"""Constants for the pi_hole integration."""

from datetime import timedelta

DOMAIN = "pi_hole"

CONF_STATISTICS_ONLY = "statistics_only"
CONF_APP_PASSWORD = "app_password"

DEFAULT_API_VERSION = 6
DEFAULT_LOCATION = "admin"
DEFAULT_METHOD = "GET"
DEFAULT_NAME = "Pi-Hole"
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_STATISTICS_ONLY = True

SERVICE_DISABLE = "disable"
SERVICE_DISABLE_ATTR_DURATION = "duration"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

VERSION_6_RESPONSE_TO_5_ERROR = {
    "key": "bad_request",
    "message": "Bad request",
    "hint": "The API is hosted at pi.hole/api, not pi.hole/admin/api",
}
