"""Constants for the iotty integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "iotty"
KNOWN_DEVICES = "known_devices"

OAUTH2_AUTHORIZE = "https://auth.iotty.com/.auth/oauth2/login"
OAUTH2_TOKEN = "https://auth.iotty.com/.auth/oauth2/token"
OAUTH2_CLIENT_ID = "hass-iotty"

IOTTYAPI_BASE = "https://homeassistant.iotty.com/"

PLATFORMS: list[Platform] = [Platform.SWITCH]

LOGGER = logging.getLogger(__package__)
