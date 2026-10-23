"""Constants for the Remote Python Debugger integration."""

from typing import Any

from homeassistant.util.hass_dict import HassKey

DOMAIN = "debugpy"
CONF_START = "start"
CONF_WAIT = "wait"
SERVICE_START = "start"

DATA_DEBUGPY_CONFIG: HassKey[dict[str, Any]] = HassKey(DOMAIN)
