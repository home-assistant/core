"""The ezbeq Profile Loader integration."""

from __future__ import annotations

import logging

from pyezbeq.consts import DEFAULT_PORT, DISCOVERY_ADDRESS
from pyezbeq.ezbeq import EzbeqClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import EzbeqCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EzBEQConfigEntry = ConfigEntry[EzbeqCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EzBEQConfigEntry) -> bool:
    """Set up ezbeq Profile Loader from a config entry."""
    _LOGGER.debug("Setting up ezbeq from a config entry")
    host = entry.data.get(CONF_HOST, DISCOVERY_ADDRESS)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    client = EzbeqClient(host=host, port=port, logger=_LOGGER)
    coordinator = EzbeqCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Finished setting up ezbeq from a config entry")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EzBEQConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ezbeq config entry")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.client.client.aclose()
    return unload_ok
