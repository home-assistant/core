"""The TED integration."""
from __future__ import annotations

import logging

import async_timeout
import tedpy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import COORDINATOR, DOMAIN, NAME, PLATFORMS
from .coordinator import TIMEOUT, TedUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TED from a config entry."""
    config = entry.data
    name = config[CONF_NAME]

    async with async_timeout.timeout(TIMEOUT):
        ted_reader = await tedpy.createTED(
            config[CONF_HOST],
            async_client=get_async_client(hass),
        )

    coordinator = TedUpdateCoordinator(hass, ted_reader=ted_reader, name=f"TED {name}")
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        NAME: name,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)
