"""Constants for Cometblue BLE thermostats."""

from typing import Final

DOMAIN: Final = "eurotronic_cometblue"
DEFAULT_NAME: Final = "Eurotronic Comet Blue"

CONF_DATETIME: Final = "datetime"
CONF_SCHEDULE: Final = "schedule"
CONF_RETRY_COUNT: Final = "retry_count"


CONF_MONDAY: Final = "monday"
CONF_TUESDAY: Final = "tuesday"
CONF_WEDNESDAY: Final = "wednesday"
CONF_THURSDAY: Final = "thursday"
CONF_FRIDAY: Final = "friday"
CONF_SATURDAY: Final = "saturday"
CONF_SUNDAY: Final = "sunday"
CONF_DELETE: Final = "delete"
CONF_START: Final = "start"
CONF_END: Final = "end"
CONF_TEMPERATURE: Final = "temperature"

CONF_ALL_DAYS: Final = {
    CONF_MONDAY,
    CONF_TUESDAY,
    CONF_WEDNESDAY,
    CONF_THURSDAY,
    CONF_FRIDAY,
    CONF_SATURDAY,
    CONF_SUNDAY,
}

CONF_ALL_TEMPERATURES: Final = {
    "currentTemp",
    "manualTemp",
    "targetTempLow",
    "targetTempHigh",
    "tempOffset",
    "windowOpen",
    "windowOpenMinutes",
}

MAX_RETRIES: Final = 3
