"""Define constants for the Growatt Server component."""

from homeassistant.const import Platform

CONF_PLANT_ID = "plant_id"

DEFAULT_PLANT_ID = "0"

DEFAULT_NAME = "Growatt"

SERVER_URLS = [
    "https://openapi.growatt.com/",  # Other regional server
    "https://openapi-cn.growatt.com/",  # Chinese server
    "https://openapi-us.growatt.com/",  # North American server
    "http://server.smten.com/",  # smten server
]

DEPRECATED_URLS = [
    "https://server.growatt.com/",
    "https://server-api.growatt.com/",
    "https://server-us.growatt.com/",
]

DEFAULT_URL = SERVER_URLS[0]

DOMAIN = "growatt_server"

PLATFORMS = [Platform.SENSOR]

LOGIN_INVALID_AUTH_CODE = "502"

SET_GRID_FIRST = "set_grid_first"
SET_BATTERY_FIRST = "set_battery_first"

DISCHARGE_POWER_RATE = "discharge_power_rate"
DISCHARGE_STOPPED_SOC = "discharge_stopped_soc"

CHARGE_POWER_RATE = "charge_power_rate"
CHARGE_STOPPED_SOC = "charge_stopped_soc"
AC_CHARGE = "ac_charge"

TIME_SLOT_1_START = "time_slot_1_start"
TIME_SLOT_1_END = "time_slot_1_end"
TIME_SLOT_1_ENABLED = "time_slot_1_enabled"
TIME_SLOT_2_START = "time_slot_2_start"
TIME_SLOT_2_END = "time_slot_2_end"
TIME_SLOT_2_ENABLED = "time_slot_2_enabled"
TIME_SLOT_3_START = "time_slot_3_start"
TIME_SLOT_3_END = "time_slot_3_end"
TIME_SLOT_3_ENABLED = "time_slot_3_enabled"
