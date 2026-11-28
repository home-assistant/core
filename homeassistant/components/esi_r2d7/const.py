"""Constants for the ESI R2D7 integration."""

import logging

from esi_r2d7 import CONNECT_ERRORS, R2D7Connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError

LOGGER = logging.getLogger(__package__)
DOMAIN = "esi_r2d7"

CONF_SYSTEM = "system"
CONF_FIRST_CHANNEL = "first_channel"
CONF_LAST_CHANNEL = "last_channel"

# HomeAssistantError: the ESPHome serial proxy raises it while it is not ready.
LINK_ERRORS = (*CONNECT_ERRORS, HomeAssistantError)

type R2D7ConfigEntry = ConfigEntry[R2D7Connection]
