"""The IntelliClima VMC integration."""

from pyintelliclima.api import IntelliClimaAPI

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER
from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator

PLATFORMS = [Platform.FAN]


async def async_setup_entry(
    hass: HomeAssistant, entry: IntelliClimaConfigEntry
) -> bool:
    """Set up IntelliClima VMC from a config entry."""
    # Create API client
    session = async_get_clientsession(hass)
    api = IntelliClimaAPI(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    # Create coordinator
    coordinator = IntelliClimaCoordinator(hass, entry, api)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    LOGGER.debug(
        "Discovered %d IntelliClima VMC device(s)",
        len(coordinator.data.ecocomfort2_devices),
    )

    # Store coordinator
    entry.runtime_data = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: IntelliClimaConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
