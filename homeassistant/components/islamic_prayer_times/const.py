"""Constants for the Islamic Prayer component."""
DOMAIN = "islamic_prayer_times"
NAME = "Islamic Prayer Times"
SENSOR_SUFFIX = "Prayer"
PRAYER_TIMES_ICON = "mdi:calendar-clock"
ATTR_TIMESTAMP = "timestamp"
TIME_STR_FORMAT = "%H:%M"

SENSOR_TYPES = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha", "Midnight"]

CONF_CALC_METHOD = "calc_method"
CONF_SENSORS = "sensors"

CALC_METHODS = ["isna", "karachi", "mwl", "makkah"]
DEFAULT_CALC_METHOD = "isna"

DATA_UPDATED = "Islamic_prayer_data_updated"
