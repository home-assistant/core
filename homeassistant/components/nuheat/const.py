"""Constants for NuHeat thermostats."""

from homeassistant.const import Platform

DOMAIN = "nuheat"

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

CONF_SERIAL_NUMBER = "serial_number"

# Options for energy calculation
CONF_FLOOR_AREA = "floor_area"
CONF_WATT_DENSITY = "watt_density"
DEFAULT_WATT_DENSITY = 12  # watts per square foot

MANUFACTURER = "NuHeat"

NUHEAT_API_STATE_SHIFT_DELAY = 2
