"""The Actron Air Neo integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER
from .coordinator import (
    ActronNeoApiClient,
    ActronNeoConfigEntry,
    ActronNeoRuntimeData,
    ActronNeoSystemCoordinator,
)

PLATFORM = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ActronNeoConfigEntry) -> bool:
    """Set up Actron Air Neo integration from a config entry."""

    api_client = ActronNeoApiClient(hass, entry)
    await api_client.async_setup()

    system_coordinators: dict[str, ActronNeoSystemCoordinator] = {}
    for system in api_client.systems:
        coordinator = ActronNeoSystemCoordinator(hass, entry, api_client, system)
        _LOGGER.debug("Setting up coordinator for system: %s", system["serial"])
        await coordinator.async_config_entry_first_refresh()
        system_coordinators[system["serial"]] = coordinator

    entry.runtime_data = ActronNeoRuntimeData(
        api_client=api_client,
        system_coordinators=system_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ActronNeoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM)
