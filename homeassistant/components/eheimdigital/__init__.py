"""The EHEIM Digital integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.LIGHT, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: EheimDigitalConfigEntry
) -> bool:
    """Set up EHEIM Digital from a config entry."""

    coordinator = EheimDigitalUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EheimDigitalConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.hub.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: EheimDigitalConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1] in config_entry.runtime_data.hub.devices
    )
