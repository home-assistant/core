"""Constants for the Nice G.O. integration."""

from datetime import timedelta

DOMAIN = "nice_go"

# Configuration
CONF_SITE_ID = "site_id"
CONF_DEVICE_ID = "device_id"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_CREATION_TIME = "refresh_token_creation_time"

REFRESH_TOKEN_EXPIRY_TIME = timedelta(days=30)
