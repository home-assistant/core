"""Constant for Plugwise component."""
DOMAIN = "plugwise"

# Default directives
DEFAULT_NAME = "Smile"
DEFAULT_USERNAME = "smile"
DEFAULT_TIMEOUT = 10
DEFAULT_PORT = 80
DEFAULT_MIN_TEMP = 4
DEFAULT_MAX_TEMP = 30
DEFAULT_SCAN_INTERVAL = {"thermostat": 60, "power": 10}

DEVICE_CLASS_GAS = "gas"

# Configuration directives
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_THERMOSTAT = "thermostat"
CONF_POWER = "power"
CONF_HEATER = "heater"
CONF_SOLAR = "solar"
CONF_GAS = "gas"

ATTR_ILLUMINANCE = "illuminance"
CURRENT_HVAC_DHW = "hot_water"
DEVICE_STATE = "device_state"

SCHEDULE_ON = "true"
SCHEDULE_OFF = "false"

# Icons
SWITCH_ICON = "mdi:electric-switch"
THERMOSTAT_ICON = "mdi:thermometer"
WATER_ICON = "mdi:water-pump"
FLAME_ICON = "mdi:fire"
COOL_ICON = "mdi:snowflake"
IDLE_ICON = "mdi:circle-off-outline"
GAS_ICON = "mdi:fire"
POWER_ICON = "mdi:flash"
POWER_FAILURE_ICON = "mdi:flash-off"
SWELL_SAG_ICON = "mdi:pulse"
VALVE_ICON = "mdi:valve"
