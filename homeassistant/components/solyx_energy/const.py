"""Constants for the Solyx Energy integration."""

DOMAIN = "solyx_energy"

# Integration variables
BASE_URL = "https://cloud.solyxenergy.nl"
REALM_ID = "solyx"
DATA_INTERVAL_SECONDS = 60

# Config entry keys
CONF_NYMO_CLIENT_ID = "nymo_client_id"
CONF_NYMO_CLIENT_SECRET = "nymo_client_secret"
CONF_NYMO_DEVICE_ID = "nymo_device_id"

# Device attributes in camelCase for mapping the HTTP API response to a device entity
ATTRIBUTE_BOILER_CURRENT = "boilerCurrent"
ATTRIBUTE_BOILER_POWER = "boilerPower"
ATTRIBUTE_BOILER_VOLTAGE = "boilerVoltage"
ATTRIBUTE_DAYS_SINCE_MAX_TEMPERATURE = "daysSinceMaximumTemperature"
ATTRIBUTE_GRID_POWER = "gridPower"
ATTRIBUTE_LEGIONELLA_DAYS = "legionellaDays"
ATTRIBUTE_SAVED_THIS_MONTH = "savedThisMonth"
ATTRIBUTE_SAVED_THIS_WEEK = "savedThisWeek"
ATTRIBUTE_SAVED_TODAY = "savedToday"
