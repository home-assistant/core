"""The Renson integration."""
from __future__ import annotations

from dataclasses import dataclass

from pyhealthbox3.healthbox3 import Healthbox3

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import RensonCoordinator

PLATFORMS = [
    Platform.SENSOR,
]




async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson from a config entry."""

    healthbox_api = None

    api_key = None

    if CONF_API_KEY in entry.data:
        api_key = entry.data[CONF_API_KEY]

    healthBoxApi = Healthbox3(
        host=entry.data[CONF_HOST],
        api_key=api_key,
        session=async_get_clientsession(hass),
    )
    if api_key:
        await healthBoxApi.async_enable_advanced_api_features()

    coordinator = RensonCoordinator("Renson", hass, healthBoxApi)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
