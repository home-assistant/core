"""The Livisi Smart Home integration."""

from __future__ import annotations

from typing import Final

from aiohttp import ClientConnectorError
from livisi.aiolivisi import AioLivisi

from homeassistant import core
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import DOMAIN
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator

PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: core.HomeAssistant, entry: LivisiConfigEntry) -> bool:
    """Set up Livisi Smart Home from a config entry."""
    web_session = aiohttp_client.async_get_clientsession(hass)
    aiolivisi = AioLivisi(web_session)
    coordinator = LivisiDataUpdateCoordinator(hass, entry, aiolivisi)
    try:
        await coordinator.async_setup()
        await coordinator.async_set_all_rooms()
    except ClientConnectorError as exception:
        raise ConfigEntryNotReady from exception

    entry.runtime_data = coordinator
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Livisi",
        name=f"SHC {coordinator.controller_type} {coordinator.serial_number}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()
    entry.async_create_background_task(
        hass, coordinator.ws_connect(), "livisi-ws_connect"
    )
    entry.async_on_unload(coordinator.websocket.disconnect)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LivisiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
