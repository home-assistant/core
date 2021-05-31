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
    "Imsak": "time",
    "Midnight": "time",
}

CONF_CALC_METHOD = "calculation_method"
CONF_SCHOOL = "school"
CONF_MIDNIGHT_MODE = "midnightMode"
CONF_LAT_ADJ_METHOD = "latitudeAdjustmentMethod"
CONF_TUNE = "tune"
CONF_IMSAK_TUNE = "imsak_tune"
CONF_FARJ_TUNE = "fajr_tune"
CONF_SUNRISE_TUNE = "sunrise_tune"
CONF_DHUHR_TUNE = "dhuhr_tune"
CONF_ASR_TUNE = "asr_tune"
CONF_MAGHRIB_TUNE = "maghrib_tune"
CONF_SUNSET_TUNE = "sunset_tune"
CONF_ISHA_TUNE = "isha_tune"
CONF_MIDNIGHT_TUNE = "midnight_tune"

CALC_METHODS = [
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

SCHOOLS = ["Shafi", "Hanafi"]
LAT_ADJ_METHODS = ["Middle of the Night", "One Seventh", "Angle Based"]
MIDNIGHT_MODES = ["Standard", "Jafari"]

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
