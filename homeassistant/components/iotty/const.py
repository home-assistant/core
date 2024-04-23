"""Constants for the iotty integration."""

from datetime import timedelta
import logging

DOMAIN = "iotty"

OAUTH2_AUTHORIZE = "https://auth.iotty.com/.auth/oauth2/login"
OAUTH2_TOKEN = "https://auth.iotty.com/.auth/oauth2/token"
OAUTH2_CLIENT_ID = "hass-iotty"

IOTTYAPI_BASE = "https://homeassistant.iotty.com/"


LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(seconds=30)
