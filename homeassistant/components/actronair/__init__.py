"""The Actron Air Neo integration."""

from actron_neo_api import (
    ActronAirNeoACSystem,
    ActronNeoAPI,
    ActronNeoAPIError,
    ActronNeoAuthError,
)

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER
from .coordinator import (
    ActronNeoConfigEntry,
    ActronNeoRuntimeData,
    ActronNeoSystemCoordinator,
)

PLATFORM = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ActronNeoConfigEntry) -> bool:
    """Set up Actron Air Neo integration from a config entry."""

    api = ActronNeoAPI(refresh_token=entry.data[CONF_API_TOKEN])
    systems: list[ActronAirNeoACSystem] = []

    try:
        systems = await api.get_ac_systems()
        await api.update_status()
    except ActronNeoAuthError:
        _LOGGER.error("Authentication error while setting up Actron Neo integration")
        raise
    except ActronNeoAPIError as err:
        _LOGGER.error("API error while setting up Actron Neo integration: %s", err)
        raise

    system_coordinators: dict[str, ActronNeoSystemCoordinator] = {}
    for system in systems:
        coordinator = ActronNeoSystemCoordinator(hass, entry, api, system)
        _LOGGER.debug("Setting up coordinator for system: %s", system["serial"])
        await coordinator.async_config_entry_first_refresh()
        system_coordinators[system["serial"]] = coordinator

    entry.runtime_data = ActronNeoRuntimeData(
        api=api,
        system_coordinators=system_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ActronNeoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM)
