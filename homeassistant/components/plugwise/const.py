"""Constant for Plugwise component."""
DOMAIN = "plugwise"

SENSOR_PLATFORMS = ["sensor"]
ALL_PLATFORMS = ["binary_sensor", "climate", "sensor", "switch"]

# Sensor mapping
SENSOR_MAP_MODEL = 0
SENSOR_MAP_UOM = 1
SENSOR_MAP_DEVICE_CLASS = 2

# Default directives
DEFAULT_NAME = "Smile"
DEFAULT_USERNAME = "smile"
DEFAULT_TIMEOUT = 10
DEFAULT_PORT = 80
DEFAULT_MIN_TEMP = 4
DEFAULT_MAX_TEMP = 30
DEFAULT_SCAN_INTERVAL = {"thermostat": 60, "power": 10}

# Configuration directives
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_THERMOSTAT = "thermostat"
CONF_POWER = "power"
CONF_HEATER = "heater"
CONF_SOLAR = "solar"
CONF_GAS = "gas"

ATTR_ILLUMINANCE = "illuminance"
UNIT_LUMEN = "lm"

CURRENT_HVAC_DHW = "hot_water"

DEVICE_STATE = "device_state"

SCHEDULE_ON = "true"
SCHEDULE_OFF = "false"

COOL_ICON = "mdi:snowflake"
FLAME_ICON = "mdi:fire"
IDLE_ICON = "mdi:circle-off-outline"
FLOW_OFF_ICON = "mdi:water-pump-off"
FLOW_ON_ICON = "mdi:water-pump"

UNDO_UPDATE_LISTENER = "undo_update_listener"
COORDINATOR = "coordinator"

ZEROCONF_MAP = {
    "smile": "P1",
    "smile_thermo": "Anna",
    "smile_open_therm": "Adam",
}
