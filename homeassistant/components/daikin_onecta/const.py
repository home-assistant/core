"""Constants for Daikin Onecta."""

from daikin_onecta.client import ONECTA_API_URL

DOMAIN = "daikin_onecta"

OAUTH2_AUTHORIZE = "https://idp.onecta.daikineurope.com/v1/oidc/authorize"
OAUTH2_TOKEN = "https://idp.onecta.daikineurope.com/v1/oidc/token"
DAIKIN_API_URL = ONECTA_API_URL

SCHEDULE_OFF = "off"

CONF_HOMEKIT_FAN_MODE_ALIASES = "homekit_fan_mode_aliases"

FANMODE_FIXED = "fixed"

SENSOR_PERIOD_DAILY = "d"
SENSOR_PERIOD_WEEKLY = "w"
SENSOR_PERIOD_YEARLY = "m"
SENSOR_PERIOD_MONTHLY = "monthly"
SENSOR_PERIODS = {
    SENSOR_PERIOD_DAILY: "Daily",
    SENSOR_PERIOD_WEEKLY: "Weekly",
    SENSOR_PERIOD_MONTHLY: "Monthly",
    SENSOR_PERIOD_YEARLY: "Yearly",
}
SENSOR_PERIOD_UNIQUE_IDS = {
    SENSOR_PERIOD_DAILY: "daily",
    SENSOR_PERIOD_WEEKLY: "weekly",
    SENSOR_PERIOD_MONTHLY: "monthly",
    SENSOR_PERIOD_YEARLY: "yearly",
}
