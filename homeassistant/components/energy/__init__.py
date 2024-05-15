"""The Energy integration."""

from __future__ import annotations

from homeassistant.components import frontend
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN
from .data import async_get_manager

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def is_configured(hass: HomeAssistant) -> bool:
    """Return a boolean to indicate if energy is configured."""
    manager = await async_get_manager(hass)
    if manager.data is None:
        return False
    return bool(manager.data != manager.default_preferences())


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Energy."""
    websocket_api.async_setup(hass)
    frontend.async_register_built_in_panel(hass, DOMAIN, DOMAIN, "mdi:lightning-bolt")

    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.SENSOR, DOMAIN, {}, config),
        eager_start=True,
    )
    hass.data[DOMAIN] = {
        "cost_sensors": {},
    }

    return True
