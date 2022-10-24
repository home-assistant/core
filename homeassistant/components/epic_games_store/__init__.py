"""The Epic Games Store integration."""
from __future__ import annotations

from epicstore_api import EpicGamesStoreAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_COUNTRY, CONF_LOCALE, DOMAIN
from .coordinator import EGSUpdateCoordinator

import logging
_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Epic Games Store from a config entry."""

    _LOGGER.error("-"*50)
    _LOGGER.warning(entry.data)
    _LOGGER.error("-"*50)
    hass.data.setdefault(DOMAIN, {})

    api = EpicGamesStoreAPI(
        entry.data[CONF_LOCALE], entry.data[CONF_COUNTRY]
    )

    coordinator = EGSUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
