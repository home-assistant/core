"""Constants for the Mawaqit Integration."""

DOMAIN = "mawaqit"

CONF_CALC_METHOD = "calculation_method"

# Config Entry

CONF_UUID: str = "uuid"

# Config Flow

CONF_SEARCH: str = "Keyword"

CONF_TYPE_SEARCH_TRANSLATION_KEY: str = "search_method_choice_translation_key"
CONF_TYPE_SEARCH: str = "search_method_choice"
CONF_TYPE_SEARCH_COORDINATES: str = "search_method_coordinates"
CONF_TYPE_SEARCH_KEYWORD: str = "search_method_keyword"

# Error messages

NO_MOSQUE_FOUND_KEYWORD = "no_mosque_found_keyword"
CANNOT_CONNECT_TO_SERVER = "cannot_connect_to_server"
WRONG_CREDENTIAL = "wrong_credential"

PRAYER_NAMES = ["fajr", "shuruq", "dhuhr", "asr", "maghrib", "isha"]
PRAYER_NAMES_IQAMA = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

# Coordinators
PRAYER_TIMES_COORDINATOR = "prayer_time_coordinator"
MOSQUES_COORDINATOR = "mosque_coordinator"
