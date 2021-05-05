"""Constants for Hive."""
ATTR_MODE = "mode"
ATTR_TIME_PERIOD = "time_period"
ATTR_ONOFF = "on_off"
CONF_CODE = "2fa"
CONFIG_ENTRY_VERSION = 1
DEFAULT_NAME = "Hive"
DOMAIN = "hive"
PLATFORMS = ["binary_sensor", "climate", "light", "sensor", "switch", "water_heater"]
PLATFORM_LOOKUP = {
    "binary_sensor": "binary_sensor",
    "climate": "climate",
    "light": "light",
    "sensor": "sensor",
    "switch": "switch",
    "water_heater": "water_heater",
}
SERVICE_BOOST_HOT_WATER = "boost_hot_water"
SERVICE_BOOST_HEATING_ON = "boost_heating_on"
SERVICE_BOOST_HEATING_OFF = "boost_heating_off"
WATER_HEATER_MODES = ["on", "off"]
