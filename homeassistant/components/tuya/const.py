"""Constants for the Tuya integration."""

CONF_BRIGHTNESS_RANGE_MODE = "brightness_range_mode"
CONF_COUNTRYCODE = "country_code"
CONF_CURR_TEMP_DIVIDER = "curr_temp_divider"
CONF_DISCOVERY_INTERVAL = "discovery_interval"
CONF_MAX_KELVIN = "max_kelvin"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_KELVIN = "min_kelvin"
CONF_MIN_TEMP = "min_temp"
CONF_QUERY_DEVICE = "query_device"
CONF_QUERY_INTERVAL = "query_interval"
CONF_SET_TEMP_DIVIDED = "set_temp_divided"
CONF_SUPPORT_COLOR = "support_color"
CONF_TEMP_DIVIDER = "temp_divider"
CONF_TEMP_STEP_OVERRIDE = "temp_step_override"
CONF_TUYA_MAX_COLTEMP = "tuya_max_coltemp"

DEFAULT_DISCOVERY_INTERVAL = 605
DEFAULT_QUERY_INTERVAL = 120
DEFAULT_TUYA_MAX_COLTEMP = 10000

DOMAIN = "tuya"

SIGNAL_CONFIG_ENTITY = "tuya_config"
SIGNAL_DELETE_ENTITY = "tuya_delete"
SIGNAL_UPDATE_ENTITY = "tuya_update"

TUYA_DATA = "tuya_data"
TUYA_DEVICES_CONF = "devices_config"
TUYA_DISCOVERY_NEW = "tuya_discovery_new_{}"

TUYA_PLATFORMS = {
    "tuya": "Tuya",
    "smart_life": "Smart Life",
    "jinvoo_smart": "Jinvoo Smart",
}

TUYA_TYPE_NOT_QUERY = ["scene", "switch"]
