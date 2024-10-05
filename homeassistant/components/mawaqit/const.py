"""Constants for the Islamic Prayer component."""

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
CONF_UUID: str = "uuid"


MAWAQIT_STORAGE_VERSION = 1
MAWAQIT_STORAGE_KEY = "mawaqit_storage"
MAWAQIT_TEST_STORAGE_KEY = "mawaqit_test_storage"

MAWAQIT_API_KEY_TOKEN = "MAWAQIT_API_KEY"
MAWAQIT_ALL_MOSQUES_NN = "all_mosques_NN"
MAWAQIT_MY_MOSQUE_NN = "my_mosque_NN"
MAWAQIT_PRAY_TIME = "pray_time"
MAWAQIT_MOSQ_LIST_DATA = "mosq_list_data"
