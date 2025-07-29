"""Constants for the Volvo integration."""

from homeassistant.const import Platform

DOMAIN = "volvo"
PLATFORMS: list[Platform] = [Platform.SENSOR]

ATTR_API_TIMESTAMP = "api_timestamp"

CONF_VIN = "vin"

DATA_BATTERY_CAPACITY = "battery_capacity_kwh"

MANUFACTURER = "Volvo"
