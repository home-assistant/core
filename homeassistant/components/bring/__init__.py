"""The Bring! integration."""

from __future__ import annotations

import logging

from bring_api import Bring

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import BringDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.TODO]

_LOGGER = logging.getLogger(__name__)

type BringConfigEntry = ConfigEntry[BringDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BringConfigEntry) -> bool:
    """Set up Bring! from a config entry."""

    session = async_get_clientsession(hass)
    bring = Bring(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    coordinator = BringDataUpdateCoordinator(hass, bring)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
