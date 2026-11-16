"""Constants for Karaca Connect."""

from homeassistant.const import Platform

DOMAIN = "karaca_connect"
CONF_DEVICE_ID = "device_id"
PLATFORMS = [Platform.SENSOR]

# Provisional: do not exceed unknown cloud rate limits.
UPDATE_INTERVAL_SECONDS = 60
