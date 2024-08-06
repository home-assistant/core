"""Constants for the Aquacell integration."""

from datetime import timedelta

DOMAIN = "aquacell"
DATA_AQUACELL = "DATA_AQUACELL"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_CREATION_TIME = "refresh_token_creation_time"

REFRESH_TOKEN_EXPIRY_TIME = timedelta(days=30)
UPDATE_INTERVAL = timedelta(days=1)
