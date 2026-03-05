"""Support for Imou devices."""

from __future__ import annotations

import logging

from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient

from homeassistant.core import HomeAssistant

from .const import API_URLS, CONF_API_URL, CONF_APP_ID, CONF_APP_SECRET, PLATFORMS
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> bool:
    """Set up Imou integration from a config entry."""
    imou_client = ImouOpenApiClient(
        entry.data[CONF_APP_ID],
        entry.data[CONF_APP_SECRET],
        API_URLS[entry.data[CONF_API_URL]],
    )
    device_manager = ImouDeviceManager(imou_client)
    imou_device_manager = ImouHaDeviceManager(device_manager)
    imou_coordinator = ImouDataUpdateCoordinator(hass, imou_device_manager, entry)
    await imou_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = imou_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
