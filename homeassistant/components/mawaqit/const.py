"""Constants for the Mawaqit Integration."""

DOMAIN = "mawaqit"
NAME = "Mawaqit Prayer Times"
PRAYER_TIMES_ICON = "mdi:calendar-clock"

SENSOR_TYPES = {
    "Fajr": "Adhan",
    "Shurouq": "Time",
    "Sunrise": "Time",
    "Dhuhr": "Adhan",
    "Asr": "Adhan",
    "Maghrib": "Adhan",
    "Isha": "Adhan",
    "Jumua": "Adhan",
    "Jumua 2": "Adhan",
    "next_mawaqit": "time",
    "Fajr Iqama": "",
    "Dhuhr Iqama": "",
    "Asr Iqama": "",
    "Maghrib Iqama": "",
    "Isha Iqama": "",
    "Next Salat Time": "",
    "Next Salat Name": "",
    "Next Salat Preparation": "",
    "Mosque_label": "",
    "Mosque_localisation": "",
    "Mosque_url": "",
    "Mosque_image": "",
}

CONF_CALC_METHOD = "calculation_method"

CALC_METHODS = ["nearest", "farthest"]
DEFAULT_CALC_METHOD = "nearest"

DATA_UPDATED = "Mawaqit_prayer_data_updated"

UPDATE_TIME = (1, 0, 0)

CONF_SERVER = "server"

USERNAME = "user"

PASSWORD = "password"

API = "api"

# Config Entry

CONF_UUID: str = "uuid"

# Config Flow

CONF_SEARCH: str = "Keyword"

CONF_TYPE_SEARCH_TRANSLATION_KEY: str = "search_method_choice_translation_key"
CONF_TYPE_SEARCH: str = "search_method_choice"
CONF_TYPE_SEARCH_COORDINATES: str = "search_method_coordinates"
CONF_TYPE_SEARCH_KEYWORD: str = "search_method_keyword"

CONF_CHOICE: str = "choice"
CONF_CHOICE_TRANSLATION_KEY: str = "choice_translation_key"
CONF_KEEP: str = "keep"
CONF_RESET: str = "reset"


# Store

MAWAQIT_STORAGE_VERSION = 1
MAWAQIT_STORAGE_KEY = "mawaqit_storage"
MAWAQIT_TEST_STORAGE_KEY = "mawaqit_test_storage"

MAWAQIT_PRAY_TIME = "pray_time"

# Error messages

NO_MOSQUE_FOUND_KEYWORD = "no_mosque_found_keyword"
CANNOT_CONNECT_TO_SERVER = "cannot_connect_to_server"
WRONG_CREDENTIAL = "wrong_credential"

PRAYER_NAMES = ["fajr", "shuruq", "dhuhr", "asr", "maghrib", "isha"]
PRAYER_NAMES_IQAMA = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

# COORDINATORS
PRAYER_TIMES_COORDINATOR = "prayer_time_coordinator"
MOSQUES_COORDINATOR = "mosque_coordinator"
