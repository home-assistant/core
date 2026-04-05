"""Integration for BIR waste collection service."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_PROPERTY_ID, DOMAIN
from .coordinator import BirConfigEntry, BirDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BirConfigEntry) -> bool:
    """Set up BIR from a config entry."""
    # Remove stale devices from previous addresses (e.g. after reconfigure)
    device_registry = dr.async_get(hass)
    expected_identifier = (DOMAIN, entry.data[CONF_PROPERTY_ID])
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if expected_identifier not in device.identifiers:
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )

    coordinator = BirDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BirConfigEntry) -> bool:
    """Unload BIR config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
