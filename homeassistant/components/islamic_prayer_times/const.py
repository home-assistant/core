"""Constants for the Islamic Prayer component."""
DOMAIN = "islamic_prayer_times"
NAME = "Islamic Prayer Times"
PRAYER_TIMES_ICON = "mdi:calendar-clock"

SENSOR_TYPES = {
    "Fajr": "prayer",
    "Sunrise": "time",
    "Dhuhr": "prayer",
    "Asr": "prayer",
    "Maghrib": "prayer",
    "Isha": "prayer",
    "Midnight": "time",
}

CONF_CALC_METHOD = "calculation_method"

CALC_METHODS = ["isna", "karachi", "mwl", "makkah", "moonsighting"]
DEFAULT_CALC_METHOD = "isna"

DATA_UPDATED = "Islamic_prayer_data_updated"
