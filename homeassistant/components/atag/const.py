"""Constants for Homeassistant."""
from homeassistant.const import DEVICE_CLASS_PRESSURE, DEVICE_CLASS_TEMPERATURE

DOMAIN = "atag"
DATA_LISTENER = "atag_listener"
SIGNAL_UPDATE_ATAG = "atag_update"
DEFAULT_PORT = 10000
DEFAULT_SCAN_INTERVAL = 30
PROJECT_URL = "https://www.atag-one.com"

UNIT_TO_CLASS = {"°C": DEVICE_CLASS_TEMPERATURE, "Bar": DEVICE_CLASS_PRESSURE}
DEFAULT_SENSORS = [
    "outside_temp",
    "outside_temp_avg",
    "weather_status",
    "operation_mode",
    "ch_water_pressure",
    "dhw_water_temp",
    "dhw_water_pres",
    "burning_hours",
    "flame_level",
]
