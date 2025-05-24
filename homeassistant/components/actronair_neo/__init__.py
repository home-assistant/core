"""The Actron Air Neo integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORM
from .coordinator import (
    ActronNeoApiCoordinator,
    ActronNeoConfigEntry,
    ActronNeoRuntimeData,
    ActronNeoSystemCoordinator,
)


async def async_setup_entry(hass: HomeAssistant, entry: ActronNeoConfigEntry) -> bool:
    """Set up Actron Air Neo integration from a config entry."""

    api_coordinator = ActronNeoApiCoordinator(hass, entry)
    await api_coordinator.async_setup()

    system_coordinators: dict[str, ActronNeoSystemCoordinator] = {}
    for system in api_coordinator.systems:
        coordinator = ActronNeoSystemCoordinator(hass, entry, api_coordinator, system)
        await coordinator.async_config_entry_first_refresh()
        system_coordinators[system["serial"]] = coordinator

    entry.runtime_data = ActronNeoRuntimeData(
        api_coordinator=api_coordinator,
        system_coordinators=system_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ActronNeoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM)
