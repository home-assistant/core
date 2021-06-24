"""The Energy integration."""
from __future__ import annotations

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Energy."""
    websocket_api.async_setup(hass)
    frontend.async_register_built_in_panel(hass, DOMAIN, DOMAIN, "hass:flash")  # type: ignore

    hass.async_create_task(
        discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )

    return True
