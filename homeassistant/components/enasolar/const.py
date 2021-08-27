#! /usr/bin/env python3
"""Constants for the EnaSolar Integration."""

from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_DAYS,
    TIME_HOURS,
)

DOMAIN = "enasolar"

DEFAULT_HOST = "my.inverter.fqdn"
DEFAULT_NAME = ""
DEFAULT_SUN_UP = "06:00"
DEFAULT_SUN_DOWN = "21:00"

CONF_HOST = "host"
CONF_NAME = "name"
CONF_CAPABILITY = "capability"
CONF_MAX_OUTPUT = "max_output"
CONF_DC_STRINGS = "dc_strings"
CONF_SUN_DOWN = "sun_down"
CONF_SUN_UP = "sun_up"

SCAN_METERS_MIN_INTERVAL = 60
SCAN_DATA_MIN_INTERVAL = 600
SCAN_MAX_INTERVAL = 3600

ENASOLAR_UNIT_MAPPINGS = {
    "": None,
    "d": TIME_DAYS,
    "h": TIME_HOURS,
    "kWh": ENERGY_KILO_WATT_HOUR,
    "W": POWER_WATT,
    "V": ELECTRIC_POTENTIAL_VOLT,
    "W/m2": IRRADIATION_WATTS_PER_SQUARE_METER,
    "C": TEMP_CELSIUS,
    "F": TEMP_FAHRENHEIT,
    "%": "%",
}
