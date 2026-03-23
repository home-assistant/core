"""The Roth Touchline SL integration."""

from __future__ import annotations

import asyncio

from pytouchlinesl import TouchlineSL

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import TouchlineSLConfigEntry, TouchlineSLModuleCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


def _migrate_device_identifiers(
    hass: HomeAssistant,
    entry: TouchlineSLConfigEntry,
    coordinators: list[TouchlineSLModuleCoordinator],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Migrate zone device identifiers from zone-only to module-aware format.

    Previously, zone devices used (DOMAIN, str(zone_id)) as their identifier.
    This caused collisions when multiple modules had zones with the same ID.
    The new format is (DOMAIN, f"{module_id}-{zone_id}").
    """
    zone_to_module: dict[str, str] = {
        str(zone_id): coordinator.data.module.id
        for coordinator in coordinators
        for zone_id in coordinator.data.zones
    }

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for identifier_domain, identifier in device.identifiers:
            if identifier_domain == DOMAIN and identifier in zone_to_module:
                module_id = zone_to_module[identifier]
                device_registry.async_update_device(
                    device.id,
                    new_identifiers={(DOMAIN, f"{module_id}-{identifier}")},
                )
                break


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

    _migrate_device_identifiers(hass, entry, coordinators, device_registry)

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
