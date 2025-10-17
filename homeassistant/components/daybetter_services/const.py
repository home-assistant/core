"""Constants for the DayBetter Services integration."""

DOMAIN = "daybetter_services"

# API constants
API_BASE_URL = "https://a.dbiot.org/daybetter/hass/api/v1.0/"

# Config flow constants
CONF_NAME = "name"
CONF_ENTITY_ID = "entity_id"

# Default values
DEFAULT_NAME = "DayBetter Service"

# Update interval
UPDATE_INTERVAL = 60  # seconds

CONF_USER_CODE = "user_code"
CONF_TOKEN = "token"


# Platforms supported by this integration
PLATFORMS = ["sensor"]
