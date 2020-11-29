"""Constant for Plugwise component."""

from homeassistant.components.switch import DEVICE_CLASS_OUTLET
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TIME_MILLISECONDS,
)

ATTR_ENABLED_DEFAULT = "enabled_default"
DOMAIN = "plugwise"
GATEWAY = "gateway"
PW_TYPE = "plugwise_type"
SMILE = "smile"
STICK = "stick"
STRETCH = "stretch"
USB = "usb"

PLATFORMS_GATEWAY = ["binary_sensor", "climate", "sensor", "switch"]
PLATFORMS_USB = ["switch"]
SENSOR_PLATFORMS = ["sensor", "switch"]
PW_TYPE = "plugwise_type"

FLOW_NET = "flow_network"
FLOW_TYPE = "flow_type"
FLOW_USB = "flow_usb"
FLOW_SMILE = "smile (Adam/Anna/P1)"
FLOW_STRETCH = "stretch (Stretch)"

# Sensor mapping
SENSOR_MAP_DEVICE_CLASS = 2
SENSOR_MAP_ICON = 3
SENSOR_MAP_MODEL = 0
SENSOR_MAP_UOM = 1

# Default directives
DEFAULT_MIN_TEMP = 4
DEFAULT_MAX_TEMP = 30
DEFAULT_NAME = "Smile"
DEFAULT_PORT = 80
DEFAULT_USERNAME = "smile"
DEFAULT_SCAN_INTERVAL = {"power": 10, "stretch": 60, "thermostat": 60}
DEFAULT_TIMEOUT = 60

# Configuration directives
CONF_BASE = "base"
CONF_GAS = "gas"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_POWER = "power"
CONF_THERMOSTAT = "thermostat"
CONF_USB_PATH = "usb_path"

ATTR_ILLUMINANCE = "illuminance"

UNIT_LUMEN = "lm"

DEVICE_STATE = "device_state"

SCHEDULE_OFF = "false"
SCHEDULE_ON = "true"

COOL_ICON = "mdi:snowflake"
FLAME_ICON = "mdi:fire"
FLOW_OFF_ICON = "mdi:water-pump-off"
FLOW_ON_ICON = "mdi:water-pump"
IDLE_ICON = "mdi:circle-off-outline"
SWITCH_ICON = "mdi:electric-switch"
NO_NOTIFICATION_ICON = "mdi:mailbox-outline"
NOTIFICATION_ICON = "mdi:mailbox-up-outline"

COORDINATOR = "coordinator"
UNDO_UPDATE_LISTENER = "undo_update_listener"
ZEROCONF_MAP = {
    "smile": "P1",
    "smile_thermo": "Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}

# Callback types
CB_NEW_NODE = "NEW_NODE"

# Sensor IDs
AVAILABLE_SENSOR_ID = "available"
CURRENT_POWER_SENSOR_ID = "power_1s"
TODAY_ENERGY_SENSOR_ID = "power_con_today"

ATTR_MAC_ADDRESS = "mac"

# Sensor types
USB_SENSORS = {
    AVAILABLE_SENSOR_ID: {
        ATTR_DEVICE_CLASS: None,
        ATTR_ENABLED_DEFAULT: False,
        ATTR_ICON: "mdi:signal-off",
        ATTR_NAME: "Available",
        ATTR_STATE: "get_available",
        ATTR_UNIT_OF_MEASUREMENT: None,
    },
    CURRENT_POWER_SENSOR_ID: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ENABLED_DEFAULT: True,
        ATTR_ICON: None,
        ATTR_NAME: "Power usage",
        ATTR_STATE: "get_power_usage",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
    },
    TODAY_ENERGY_SENSOR_ID: {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ENABLED_DEFAULT: True,
        ATTR_ICON: None,
        ATTR_NAME: "Power consumption today",
        ATTR_STATE: "get_power_consumption_today",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
    },
}

# Switch types
USB_SWITCHES = {
    "relay": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_OUTLET,
        ATTR_ENABLED_DEFAULT: True,
        ATTR_ICON: None,
        ATTR_NAME: "Relay state",
        ATTR_STATE: "get_relay_state",
        "switch": "set_relay_state",
        ATTR_UNIT_OF_MEASUREMENT: "state",
    }
}
