"""The Livisi Smart Home integration."""
from __future__ import annotations

import asyncio
from typing import Final

from aiolivisi import AioLivisi

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import DOMAIN, SWITCH_PLATFORM
from .coordinator import LivisiDataUpdateCoordinator
from .shc import SHC

PLATFORMS: Final = [SWITCH_PLATFORM]


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Livisi Smart Home from a config entry."""
    web_session = aiohttp_client.async_get_clientsession(hass)
    aiolivisi = AioLivisi(web_session)
    coordinator = LivisiDataUpdateCoordinator(hass, aiolivisi)
    controller: SHC = SHC(
        hass=hass, config_entry=entry, coordinator=coordinator, aiolivisi=aiolivisi
    )
    await controller.async_setup()
    await controller.async_set_all_rooms()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=controller.serial_number,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Livisi",
        name=f"SHC {controller.controller_type} {controller.serial_number}",
        sw_version=controller.os_version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()
    asyncio.create_task(controller.ws_connect())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]

    unload_success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await controller.websocket.disconnect()
    if unload_success:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_success
