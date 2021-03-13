"""Constant for Plugwise component."""
DOMAIN = "plugwise"

SENSOR_PLATFORMS = ["sensor", "switch"]
PLATFORMS_GATEWAY = ["binary_sensor", "climate", "sensor", "switch"]
PW_TYPE = "plugwise_type"
GATEWAY = "gateway"

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
CONF_GAS = "gas"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_POWER = "power"
CONF_THERMOSTAT = "thermostat"

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
