"""Constants for Plugwise beta component."""

import voluptuous as vol
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.helpers import config_validation as cv

API = "api"
ATTR_ENABLED_DEFAULT = "enabled_default"
DOMAIN = "plugwise"
COORDINATOR = "coordinator"
FW = "fw"
GATEWAY = "gateway"
ID = "id"
PW_CLASS = "class"
PW_LOCATION = "location"
PW_MODEL = "model"
PW_TYPE = "plugwise_type"
SCHEDULE_OFF = "false"
SCHEDULE_ON = "true"
SMILE = "smile"
STICK = "stick"
STRETCH = "stretch"
STRETCH_USERNAME = "stretch"
VENDOR = "vendor"
UNIT_LUMEN = "lm"
USB = "usb"

FLOW_NET = "Network: Smile/Stretch"
FLOW_SMILE = "Smile (Adam/Anna/P1)"
FLOW_STRETCH = "Stretch (Stretch)"
FLOW_TYPE = "flow_type"
FLOW_USB = "USB: Stick"

UNDO_UPDATE_LISTENER = "undo_update_listener"

# Default directives
DEFAULT_MAX_TEMP = 30
DEFAULT_MIN_TEMP = 4
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = {
    "power": 10,
    "stretch": 60,
    "thermostat": 60,
}
DEFAULT_TIMEOUT = 10
DEFAULT_USERNAME = "smile"

# --- Const for Plugwise Smile and Stretch
GATEWAY_PLATFORMS = [BINARY_SENSOR_DOMAIN, CLIMATE_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]
SENSOR_PLATFORMS = [SENSOR_DOMAIN, SWITCH_DOMAIN]
SEVERITIES = ["other", "info", "warning", "error"]

# Climate const:
MASTER_THERMOSTATS = [
    "thermostat",
    "zone_thermometer",
    "zone_thermostat",
    "thermostatic_radiator_valve",
]

# Config_flow const:
ZEROCONF_MAP = {
    "smile": "P1",
    "smile_thermo": "Anna",
    "smile_open_therm": "Adam",
    "stretch": "Stretch",
}

# Icons
COOLING_ICON = "mdi:snowflake"
FLAME_ICON = "mdi:fire"
FLOW_OFF_ICON = "mdi:water-pump-off"
FLOW_ON_ICON = "mdi:water-pump"
HEATING_ICON = "mdi:radiator"
IDLE_ICON = "mdi:circle-off-outline"
NOTIFICATION_ICON = "mdi:mailbox-up-outline"
NO_NOTIFICATION_ICON = "mdi:mailbox-outline"
SWITCH_ICON = "mdi:electric-switch"

# Binary Sensors:
DHW_STATE = "dhw_state"
FLAME_STATE = "flame_state"
PW_NOTIFICATION = "plugwise_notification"
SLAVE_BOILER_STATE = "slave_boiler_state"

# Sensors:
BATTERY = "battery"
CURRENT_TEMP = "temperature"
DEVICE_STATE = "device_state"
EL_CONSUMED = "electricity_consumed"
EL_CONSUMED_INTERVAL = "electricity_consumed_interval"
EL_CONSUMED_OFF_PEAK_CUMULATIVE = "electricity_consumed_off_peak_cumulative"
EL_CONSUMED_OFF_PEAK_INTERVAL = "electricity_consumed_off_peak_interval"
EL_CONSUMED_OFF_PEAK_POINT = "electricity_consumed_off_peak_point"
EL_CONSUMED_PEAK_CUMULATIVE = "electricity_consumed_peak_cumulative"
EL_CONSUMED_PEAK_INTERVAL = "electricity_consumed_peak_interval"
EL_CONSUMED_PEAK_POINT = "electricity_consumed_peak_point"
EL_CONSUMED_POINT = "electricity_consumed_point"
EL_PRODUCED = "electricity_produced"
EL_PRODUCED_INTERVAL = "electricity_produced_interval"
EL_PRODUCED_OFF_PEAK_CUMULATIVE = "electricity_produced_off_peak_cumulative"
EL_PRODUCED_OFF_PEAK_INTERVAL = "electricity_produced_off_peak_interval"
EL_PRODUCED_OFF_PEAK_POINT = "electricity_produced_off_peak_point"
EL_PRODUCED_PEAK_CUMULATIVE = "electricity_produced_peak_cumulative"
EL_PRODUCED_PEAK_INTERVAL = "electricity_produced_peak_interval"
EL_PRODUCED_PEAK_POINT = "electricity_produced_peak_point"
EL_PRODUCED_POINT = "electricity_produced_point"
GAS_CONSUMED_CUMULATIVE = "gas_consumed_cumulative"
GAS_CONSUMED_INTERVAL = "gas_consumed_interval"
HUMIDITY = "humidity"
INTENDED_BOILER_TEMP = "intended_boiler_temperature"
MOD_LEVEL = "modulation_level"
NET_EL_CUMULATIVE = "net_electricity_cumulative"
NET_EL_POINT = "net_electricity_point"
OUTDOOR_TEMP = "outdoor_temperature"
RETURN_TEMP = "return_temperature"
TARGET_TEMP = "setpoint"
TEMP_DIFF = "temperature_difference"
VALVE_POS = "valve_position"
WATER_PRESSURE = "water_pressure"
WATER_TEMP = "water_temperature"

# Switches
DHW_COMF_MODE = "dhw_cm_switch"
LOCK = "lock"
RELAY = "relay"


# PLACEHOLDER --- Const for Plugwise USB-stick.

