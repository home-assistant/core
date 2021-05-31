"""Constants for the Islamic Prayer component."""
from typing import Final

DOMAIN: Final = "islamic_prayer_times"
NAME: Final = "Islamic Prayer Times"
PRAYER_TIMES_ICON: Final = "mdi:calendar-clock"

SENSOR_TYPES: Final = {
    "Fajr": "prayer",
    "Sunrise": "time",
    "Dhuhr": "prayer",
    "Asr": "prayer",
    "Maghrib": "prayer",
    "Isha": "prayer",
    "Imsak": "time",
    "Midnight": "time",
}

CONF_CALC_METHOD: Final = "calculation_method"
CONF_SCHOOL: Final = "school"
CONF_MIDNIGHT_MODE: Final = "midnightMode"
CONF_LAT_ADJ_METHOD: Final = "latitudeAdjustmentMethod"
CONF_TUNE: Final = "tune"
CONF_IMSAK_TUNE: Final = "imsak_tune"
CONF_FARJ_TUNE: Final = "fajr_tune"
CONF_SUNRISE_TUNE: Final = "sunrise_tune"
CONF_DHUHR_TUNE: Final = "dhuhr_tune"
CONF_ASR_TUNE: Final = "asr_tune"
CONF_MAGHRIB_TUNE: Final = "maghrib_tune"
CONF_SUNSET_TUNE: Final = "sunset_tune"
CONF_ISHA_TUNE: Final = "isha_tune"
CONF_MIDNIGHT_TUNE: Final = "midnight_tune"

CALC_METHODS: Final = [
    "ISNA",
    "Makkah",
    "MWL",
    "karachi",
    "Egypt",
    "Tehran",
    "Gulf",
    "Kuwait",
    "Qatar",
    "Singapore",
    "France",
    "Turkey",
    "Russia",
]

SCHOOLS: Final = ["Shafi", "Hanafi"]
LAT_ADJ_METHODS: Final = ["Middle of the Night", "One Seventh", "Angle Based"]
MIDNIGHT_MODES: Final = ["Standard", "Jafari"]

TIMES_TUNE = [
    CONF_IMSAK_TUNE,
    CONF_FARJ_TUNE,
    CONF_SUNRISE_TUNE,
    CONF_DHUHR_TUNE,
    CONF_ASR_TUNE,
    CONF_MAGHRIB_TUNE,
    CONF_SUNSET_TUNE,
    CONF_ISHA_TUNE,
    CONF_MIDNIGHT_TUNE,
]

DEFAULT_CALC_METHOD = "ISNA"
DEFAULT_SCHOOL = "Shafi"
DEFAULT_MIDNIGHT_MODE = "Standard"
DEFAULT_LAT_ADJ_METHOD = "Angle Based"


# DATA_UPDATED = "Islamic_prayer_data_updated"
