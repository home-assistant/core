"""Constants for the iotty integration."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "iotty"

OAUTH2_AUTHORIZE = "https://auth.iotty.com/.auth/oauth2/login"
OAUTH2_TOKEN = "https://auth.iotty.com/.auth/oauth2/token"
OAUTH2_CLIENT_ID = "hass-iotty"

IOTTYAPI_BASE = "https://homeassistant.iotty.com/"

PLATFORMS: list[Platform] = [Platform.SWITCH]

LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(seconds=30)
