"""The Met Office Weather Warnings integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import MetOfficeWarningsConfigEntry, MetOfficeWarningsCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: MetOfficeWarningsConfigEntry
) -> bool:
    """Set up Met Office Weather Warnings from a config entry."""
    session = async_get_clientsession(hass)
    coordinator = MetOfficeWarningsCoordinator(hass, entry, session)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MetOfficeWarningsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
