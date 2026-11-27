"""Constants for the Volvo integration."""

from homeassistant.const import Platform

DOMAIN = "volvo"
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.SENSOR,
]

API_NONE_VALUE = "UNSPECIFIED"
CONF_VIN = "vin"
DATA_BATTERY_CAPACITY = "battery_capacity_kwh"
MANUFACTURER = "Volvo"
VOLVO_DEV_PORTAL_URL = "https://developer.volvocars.com/account/#your-api-applications"
