"""Constants for Hive."""
from homeassistant.const import Platform

ATTR_MODE = "mode"
ATTR_TIME_PERIOD = "time_period"
ATTR_ONOFF = "on_off"
CONF_CODE = "2fa"
CONF_DEVICE_NAME = "device_name"
CONFIG_ENTRY_VERSION = 1
DEFAULT_NAME = "Hive"
DOMAIN = "hive"
PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]
PLATFORM_LOOKUP = {
    Platform.ALARM_CONTROL_PANEL: "alarm_control_panel",
    Platform.BINARY_SENSOR: "binary_sensor",
    Platform.CLIMATE: "climate",
    Platform.LIGHT: "light",
    Platform.SENSOR: "sensor",
    Platform.SWITCH: "switch",
    Platform.WATER_HEATER: "water_heater",
}
SERVICE_BOOST_HOT_WATER = "boost_hot_water"
SERVICE_BOOST_HEATING_ON = "boost_heating_on"
SERVICE_BOOST_HEATING_OFF = "boost_heating_off"
WATER_HEATER_MODES = ["on", "off"]
