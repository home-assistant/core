"""The Actron Air integration."""

from actron_neo_api import (
    ActronAirACSystem,
    ActronAirAPI,
    ActronAirAPIError,
    ActronAirAuthError,
)

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER
from .coordinator import (
    ActronAirConfigEntry,
    ActronAirRuntimeData,
    ActronAirSystemCoordinator,
)

PLATFORM = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ActronAirConfigEntry) -> bool:
    """Set up Actron Air integration from a config entry."""

    api = ActronAirAPI(refresh_token=entry.data[CONF_API_TOKEN])
    systems: list[ActronAirACSystem] = []

    try:
        systems = await api.get_ac_systems()
        await api.update_status()
    except ActronAirAuthError:
        _LOGGER.error("Authentication error while setting up Actron Air integration")
        raise
    except ActronAirAPIError as err:
        _LOGGER.error("API error while setting up Actron Air integration: %s", err)
        raise

    system_coordinators: dict[str, ActronAirSystemCoordinator] = {}
    for system in systems:
        coordinator = ActronAirSystemCoordinator(hass, entry, api, system)
        _LOGGER.debug("Setting up coordinator for system: %s", system["serial"])
        await coordinator.async_config_entry_first_refresh()
        system_coordinators[system["serial"]] = coordinator

    entry.runtime_data = ActronAirRuntimeData(
        api=api,
        system_coordinators=system_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ActronAirConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM)
