"""The Axle Energy integration."""

from aioaxlevpp import AxleClient

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import AxleConfigEntry, AxleCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: AxleConfigEntry) -> bool:
    """Set up Axle Energy from a config entry."""
    coordinator = AxleCoordinator(
        hass, entry, AxleClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AxleConfigEntry) -> bool:
    """Unload Axle Energy."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
