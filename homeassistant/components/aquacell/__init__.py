"""The Aquacell integration."""
from __future__ import annotations

import logging

from aioaquacell import AquacellApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DATA_AQUACELL, DOMAIN
from .coordinator import Coordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aquacell from a config entry."""
    session = async_get_clientsession(hass)

    aquacell_api = AquacellApi(session)
    refresh_token = entry.data[CONF_ACCESS_TOKEN]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_AQUACELL: aquacell_api}

    coordinator = Coordinator(hass, aquacell_api, refresh_token)

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
