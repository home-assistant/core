"""The Ecoforest integration."""

from __future__ import annotations

import logging

import httpx
from pyecoforest.api import EcoforestApi
from pyecoforest.exceptions import (
    EcoforestAuthenticationRequired,
    EcoforestConnectionError,
)

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import EcoforestConfigEntry, EcoforestCoordinator

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: EcoforestConfigEntry) -> bool:
    """Set up Ecoforest from a config entry."""

    host = entry.data[CONF_HOST]
    auth = httpx.BasicAuth(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    api = EcoforestApi(host, auth)

    try:
        device = await api.get()
        _LOGGER.debug("Ecoforest: %s", device)
    except EcoforestAuthenticationRequired:
        _LOGGER.error("Authentication on device %s failed", host)
        return False
    except EcoforestConnectionError as err:
        _LOGGER.error("Error communicating with device %s", host)
        raise ConfigEntryNotReady from err

    coordinator = EcoforestCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcoforestConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
