"""The Ecoforest integration."""
from __future__ import annotations

import httpx
from pyecoforest.api import EcoforestApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EcoforestCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ecoforest from a config entry."""

    host = entry.data[CONF_HOST]
    auth = httpx.BasicAuth(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    api = EcoforestApi(host, auth)
    coordinator = EcoforestCoordinator(hass, api, host)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
