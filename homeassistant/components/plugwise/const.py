"""Constants for Plugwise component."""

API = "api"
ATTR_ILLUMINANCE = "illuminance"
COORDINATOR = "coordinator"
DEVICE_STATE = "device_state"
DOMAIN = "plugwise"
FLOW_NET = "Network: Smile/Stretch"
FLOW_SMILE = "smile (Adam/Anna/P1)"
FLOW_STRETCH = "stretch (Stretch)"
FLOW_TYPE = "flow_type"
FLOW_USB = "USB: Stick - Coming soon"
GATEWAY = "gateway"
PW_TYPE = "plugwise_type"
SCHEDULE_OFF = "false"
SCHEDULE_ON = "true"
SMILE = "smile"
STRETCH = "stretch"
STRETCH_USERNAME = "stretch"
UNDO_UPDATE_LISTENER = "undo_update_listener"
UNIT_LUMEN = "lm"

PLATFORMS_GATEWAY = ["binary_sensor", "climate", "sensor", "switch"]
SENSOR_PLATFORMS = ["sensor", "switch"]
ZEROCONF_MAP = {
    "smile": "P1",
    "smile_thermo": "Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}

# Sensor mapping
SENSOR_MAP_DEVICE_CLASS = 2
SENSOR_MAP_ICON = 3
SENSOR_MAP_MODEL = 0
SENSOR_MAP_UOM = 1

# Default directives
DEFAULT_MAX_TEMP = 30
DEFAULT_MIN_TEMP = 4
DEFAULT_NAME = "Smile"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = {
    "power": 10,
    "stretch": 60,
    "thermostat": 60,
}
DEFAULT_TIMEOUT = 60
DEFAULT_USERNAME = "smile"

# Configuration directives
CONF_GAS = "gas"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_POWER = "power"
CONF_THERMOSTAT = "thermostat"

# Icons
COOL_ICON = "mdi:snowflake"
FLAME_ICON = "mdi:fire"
FLOW_OFF_ICON = "mdi:water-pump-off"
FLOW_ON_ICON = "mdi:water-pump"
IDLE_ICON = "mdi:circle-off-outline"
SWITCH_ICON = "mdi:electric-switch"
NO_NOTIFICATION_ICON = "mdi:mailbox-outline"
NOTIFICATION_ICON = "mdi:mailbox-up-outline"
