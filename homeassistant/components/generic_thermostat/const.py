"""Constants for the Generic Thermostat helper."""

from homeassistant.const import Platform

DOMAIN = "generic_thermostat"
PLATFORMS = [Platform.CLIMATE]

CONF_AC_MODE = "ac_mode"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HEATER = "heater"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_MIN_DUR = "min_cycle_duration"
CONF_SENSOR = "target_sensor"
