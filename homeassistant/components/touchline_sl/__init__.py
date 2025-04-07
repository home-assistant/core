"""The Roth Touchline SL integration."""

from __future__ import annotations

import asyncio

from pytouchlinesl import TouchlineSL

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import TouchlineSLConfigEntry, TouchlineSLModuleCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineSLConfigEntry) -> bool:
    """Set up Roth Touchline SL from a config entry."""
    account = TouchlineSL(
        username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )

    coordinators: list[TouchlineSLModuleCoordinator] = [
        TouchlineSLModuleCoordinator(hass, entry, module)
        for module in await account.modules()
    ]

    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )

    device_registry = dr.async_get(hass)

    # Create a new Device for each coorodinator to represent each module
    for c in coordinators:
        module = c.data.module
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, module.id)},
            name=module.name,
            manufacturer="Roth",
            model=module.type,
            sw_version=module.version,
        )

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TouchlineSLConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
