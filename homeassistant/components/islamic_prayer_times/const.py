"""Constants for the Islamic Prayer component."""
DOMAIN = "islamic_prayer_times"
NAME = "Islamic Prayer Times"
PRAYER_TIMES_ICON = "mdi:calendar-clock"

SENSOR_TYPES = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha", "midnight"]

CONF_CALC_METHOD = "calculation_method"
CONF_SENSORS = "sensors"

CALC_METHODS = ["karachi", "isna", "mwl", "makkah"]
DEFAULT_CALC_METHOD = "isna"

DATA_UPDATED = "Islamic_prayer_data_updated"
