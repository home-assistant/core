"""Constants for Hive."""
DEFAULT_NAME = "Hive"
DOMAIN = "hive"
CONF_CODE = "2fa"
CONFIG_ENTRY_VERSION = 1
ATTR_AVAILABLE = "available"
ATTR_MODE = "mode"
DOMAIN = "hive"
SERVICES = ["heating", "hotwater", "trvcontrol"]
SERVICE_BOOST_HOT_WATER = "boost_hot_water"
SERVICE_BOOST_HEATING = "boost_heating"
ATTR_TIME_PERIOD = "time_period"
ATTR_ONOFF = "on_off"
PLATFORMS = ["binary_sensor", "climate", "light", "sensor", "switch", "water_heater"]
PLATFORM_LOOKUP = {
    "binary_sensor": "binary_sensor",
    "climate": "climate",
    "light": "light",
    "sensor": "sensor",
    "switch": "switch",
    "water_heater": "water_heater",
}
