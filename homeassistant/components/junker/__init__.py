"""The Junker integration."""

from junker_api import JunkerClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_AREA_ID, CONF_MUNICIPALITY
from .coordinator import JunkerConfigEntry, JunkerDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: JunkerConfigEntry) -> None:
    """Set up Junker from a config entry."""
    client = JunkerClient(
        async_get_clientsession(hass),
        entry.data[CONF_MUNICIPALITY],
        entry.data.get(CONF_AREA_ID),
    )
    coordinator = JunkerDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: JunkerConfigEntry) -> None:
    """Unload a Junker config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
