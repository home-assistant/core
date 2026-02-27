"""The Sharp COCORO Air integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS
from .coordinator import SharpCocoroAirCoordinator

type SharpCocoroAirConfigEntry = ConfigEntry[SharpCocoroAirCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharpCocoroAirConfigEntry,
) -> bool:
    """Set up Sharp COCORO Air from a config entry."""
    coordinator = SharpCocoroAirCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_remove_stale_devices(hass, entry)
    return True


def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: SharpCocoroAirConfigEntry,
) -> None:
    """Remove devices that are no longer returned by the API."""
    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)
    existing_entries = dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    )
    current_device_ids = set(coordinator.data)
    for device_entry in existing_entries:
        device_id = next(
            (
                identifier[1]
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
            ),
            None,
        )
        if device_id is not None and device_id not in current_device_ids:
            device_registry.async_remove_device(device_entry.id)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SharpCocoroAirConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
