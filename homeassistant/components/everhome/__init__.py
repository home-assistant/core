"""The EcoTracker integration."""

from ecotracker import EcoTracker

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import EcoTrackerConfigEntry, EcoTrackerDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EcoTrackerConfigEntry) -> bool:
    """Set up EcoTracker from a config entry."""

    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)
    client = EcoTracker(host, session=session)

    coordinator = EcoTrackerDataUpdateCoordinator(
        hass,
        client=client,
        host=host,
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcoTrackerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
