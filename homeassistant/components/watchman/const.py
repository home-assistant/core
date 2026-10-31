"""Constants for Kingspan Watchman SENSiT."""

from homeassistant.const import Platform

# Base component constants
MANUFACTURER = "Kingspan"
MODEL = "Watchman SENSiT"
DOMAIN = "watchman"
DOMAIN_DATA = f"{DOMAIN}_data"
PLATFORMS: list[Platform] = [Platform.SENSOR]

ATTRIBUTION = "Data provided by https://www.connectsensor.com/"
ISSUE_URL = "https://github.com/masaccio/ha-kingspan-watchman-sensit/issues"

# Configuration and options
CONF_USAGE_WINDOW = "usage_window"
CONF_OIL_ENERGY_DENSITY = "oil_energy_density"

# Defaults
API_TIMEOUT = 30  # seconds
REFILL_THRESHOLD = 1.1  # factor considered a tank refill
DEFAULT_TANK_NAME = "My Tank"
DEFAULT_USAGE_WINDOW = 14  # days
DEFAULT_UPDATE_INTERVAL = 8  # hours
DEFAULT_OIL_ENERGY_DENSITY = 9.8  # kWh per litre
