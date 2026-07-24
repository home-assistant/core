"""Constants for the Solyx Energy integration."""

DOMAIN = "solyx_energy"

# Integration variables
BASE_URL = "https://cloud.solyxenergy.nl"
REALM_ID = "solyx"
DATA_INTERVAL_SECONDS = 60
DATA_SETTLE_SECONDS = 2

# Config entry keys
CONF_NYMO_CLIENT_ID = "nymo_client_id"
CONF_NYMO_CLIENT_SECRET = "nymo_client_secret"
CONF_NYMO_DEVICE_ID = "nymo_device_id"

# Device attributes in camelCase for mapping the HTTP API response to a device entity
ATTRIBUTE_POWER_BOILER = "powerBoiler"
ATTRIBUTE_ENERGY_BOILER = "energyBoiler"
ATTRIBUTE_OPERATING_MODE = "operatingMode"
ATTRIBUTE_GRID_POWER = "gridPower"
ATTRIBUTE_CONTROL_VALUE = "controlValue"
