"""Constants for the Volvo integration."""

from homeassistant.const import Platform

DOMAIN = "volvo"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

API_NONE_VALUE = "UNSPECIFIED"
CONF_VIN = "vin"
DATA_BATTERY_CAPACITY = "battery_capacity_kwh"
MANUFACTURER = "Volvo"
