"""The Aussie Broadband integration."""
from __future__ import annotations

import requests
from aussiebb import AussieBB, AuthenticationException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .const import ATTR_PASSWORD, ATTR_USERNAME, DOMAIN
from ...exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed

PLATFORMS = ["sensor", "camera"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Aussie Broadband component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""

    def create_client():
        try:
            return AussieBB(entry.data[ATTR_USERNAME], entry.data[ATTR_PASSWORD])
        except AuthenticationException:
            raise ConfigEntryAuthFailed()
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError):
            raise ConfigEntryNotReady()

    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(create_client)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
