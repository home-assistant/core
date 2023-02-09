"""The zcs_azzurro integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SCHEMA_CLIENT_KEY, SCHEMA_FRIENDLY_NAME, SCHEMA_THINGS_KEY
from .zcs_azzurro_api import ZcsAzzurroApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up zcs_azzurro from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = ZcsAzzurroApi(
        client=entry.data[SCHEMA_CLIENT_KEY],
        thing_serial=entry.data[SCHEMA_THINGS_KEY],
        name=entry.data[SCHEMA_FRIENDLY_NAME],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ResponseError(HomeAssistantError):
    """Error to indicate there was a not ok response."""
