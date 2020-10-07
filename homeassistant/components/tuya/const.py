"""Constants for the Tuya integration."""

CONF_BRIGHTNESS_RANGE_MODE = "brightness_range_mode"
CONF_COUNTRYCODE = "country_code"
CONF_CURR_TEMP_DIVIDER = "curr_temp_divider"
CONF_DEVICE_NAME = "device_name"
CONF_DISCOVERY_INTERVAL = "discovery_interval"
CONF_EXT_TEMP_SENSOR = "ext_temp_sensor"
CONF_MAX_KELVIN = "max_kelvin"
CONF_MAX_TUYA_TEMP = "max_tuya_temp"
CONF_MIN_KELVIN = "min_kelvin"
CONF_QUERY_INTERVAL = "query_interval"
CONF_SUPPORT_COLOR = "support_color"
CONF_TEMP_DIVIDER = "temp_divider"

DEFAULT_DISCOVERY_INTERVAL = 605.0
DEFAULT_QUERY_INTERVAL = 120.0

DOMAIN = "tuya"

TUYA_DATA = "tuya_data"
TUYA_DEVICES_CONF = "devices_config"
TUYA_DISCOVERY_NEW = "tuya_discovery_new_{}"

TUYA_PLATFORMS = {
    "tuya": "Tuya",
    "smart_life": "Smart Life",
    "jinvoo_smart": "Jinvoo Smart",
}
