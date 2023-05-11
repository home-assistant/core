"""Constants for the PID thermostat integration."""
from homeassistant.components.climate import ClimateEntityFeature

DOMAIN = "pid_thermostat"
PLATFORMS = ["climate"]

CONF_HEATER = "heater"
CONF_SENSOR = "target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_AC_MODE = "ac_mode"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_AWAY_TEMP = "away_temp"

AC_MODE_COOL = "cool"
AC_MODE_HEAT = "heat"


DEFAULT_NAME = "PID Thermostat"
DEFAULT_CYCLE_TIME = {"minutes": 5}
DEFAULT_PID_KP = 100.0
DEFAULT_PID_KI = 0.1
DEFAULT_PID_KD = 0.0
DEFAULT_AC_MODE = AC_MODE_HEAT

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE
