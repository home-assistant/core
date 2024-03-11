"""Constants for the Islamic Prayer component."""

from typing import Final

DOMAIN: Final = "islamic_prayer_times"
NAME: Final = "Islamic Prayer Times"

CONF_CALC_METHOD: Final = "calculation_method"

CALC_METHODS: Final = [
    "jafari",
    "karachi",
    "isna",
    "mwl",
    "makkah",
    "egypt",
    "tehran",
    "gulf",
    "kuwait",
    "qatar",
    "singapore",
    "france",
    "turkey",
    "russia",
    "moonsighting",
    "custom",
]
DEFAULT_CALC_METHOD: Final = "isna"

CONF_LAT_ADJ_METHOD: Final = "latitude_adjustment_method"
LAT_ADJ_METHODS: Final = ["middle_of_the_night", "one_seventh", "angle_based"]
DEFAULT_LAT_ADJ_METHOD: Final = "middle_of_the_night"

CONF_MIDNIGHT_MODE: Final = "midnight_mode"
MIDNIGHT_MODES: Final = ["standard", "jafari"]
DEFAULT_MIDNIGHT_MODE: Final = "standard"

CONF_SCHOOL: Final = "school"
SCHOOLS: Final = ["shafi", "hanafi"]
DEFAULT_SCHOOL: Final = "shafi"
