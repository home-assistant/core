"""Vaillant component constants."""
from datetime import timedelta

# constants used in hass.data
DOMAIN = "vaillant"
HUB = "hub"
ENTITIES = "entities"

# list of platforms into entity are created
# PLATFORMS = ["binary_sensor", "sensor", "climate", "water_heater"]
PLATFORMS = ["binary_sensor", "sensor", "water_heater", "climate"]

# default values for configuration
DEFAULT_EMPTY = ""
DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)
DEFAULT_QUICK_VETO_DURATION = 3 * 60
DEFAULT_SMART_PHONE_ID = "homeassistant"

# max and min values for configuration
MIN_SCAN_INTERVAL = timedelta(minutes=1)
MIN_QUICK_VETO_DURATION = 0.5 * 60
MAX_QUICK_VETO_DURATION = 24 * 60

# configuration keys
CONF_QUICK_VETO_DURATION = "quick_veto_duration"
CONF_SMARTPHONE_ID = "smartphoneid"
CONF_SERIAL_NUMBER = "serial_number"

# constants for states_attributes
ATTR_VAILLANT_MODE = "vaillant_mode"
ATTR_VAILLANT_SETTING = "setting"
ATTR_VAILLANT_NEXT_SETTING = "next_setting"
ATTR_ENDS_AT = "ends_at"
ATTR_QUICK_MODE = "quick_mode"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_TEMPERATURE = "temperature"
ATTR_DURATION = "duration"
