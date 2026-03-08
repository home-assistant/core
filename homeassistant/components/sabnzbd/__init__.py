"""Support for monitoring an SABnzbd NZB client."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import SabnzbdConfigEntry, SabnzbdUpdateCoordinator
from .helpers import get_client

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SabnzbdConfigEntry) -> bool:
    """Set up the SabNzbd Component."""

    sab_api = await get_client(hass, entry.data)
    if not sab_api:
        raise ConfigEntryNotReady

    coordinator = SabnzbdUpdateCoordinator(hass, entry, sab_api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SabnzbdConfigEntry) -> bool:
    """Unload a Sabnzbd config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
