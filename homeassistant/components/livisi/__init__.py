"""The Livisi Smart Home integration."""
from __future__ import annotations

from typing import Final

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SWITCH_PLATFORM
from .shc import SHC

PLATFORMS: Final = [SWITCH_PLATFORM]


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Livisi Smart Home from a config entry."""

    controller: SHC = SHC(hass, entry)
    await controller.async_setup()
    await controller.async_set_devices()
    await controller.async_set_all_rooms()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Livisi",
        name=f"SHC {controller.controller_type} {controller.serial_number}",
        sw_version=controller.os_version,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    hass.loop.create_task(controller.ws_connect())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]

    unload_success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_success:
        hass.data[DOMAIN].pop(entry.entry_id)

    await controller.websocket.disconnect()

    return unload_success
