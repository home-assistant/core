"""The OpenGarage integration."""

from __future__ import annotations

import opengarage

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_KEY
from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpenGarageConfigEntry) -> bool:
    """Set up OpenGarage from a config entry."""
    open_garage_connection = opengarage.OpenGarage(
        f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        entry.data[CONF_DEVICE_KEY],
        entry.data[CONF_VERIFY_SSL],
        async_get_clientsession(hass),
    )
    open_garage_data_coordinator = OpenGarageDataUpdateCoordinator(
        hass, entry, open_garage_connection
    )
    await open_garage_data_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = open_garage_data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenGarageConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
