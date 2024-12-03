"""The Compit integration."""

from __future__ import annotations

import asyncio
import logging

from compit_inext_api import CompitAPI, DeviceDefinitionsLoader

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import CompitDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Compit from a config entry."""

    session = async_get_clientsession(hass)
    api = CompitAPI(entry.data["email"], entry.data["password"], session)
    gates = await api.authenticate()
    device_definitions = await DeviceDefinitionsLoader.get_device_definitions(
        hass.config.language
    )

    if gates is False:
        return False

    coordinator = CompitDataUpdateCoordinator(
        hass, gates.gates, api, device_definitions
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    for platform in PLATFORMS:
        coordinator.platforms.append(platform)
        await hass.config_entries.async_forward_entry_setup(entry, platform)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry for the Compit integration."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
