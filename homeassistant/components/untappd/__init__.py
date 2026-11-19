"""The Untappd integration."""

from aiountappd import UntappdClient

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import UntappdConfigEntry, UntappdDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: UntappdConfigEntry) -> None:
    """Set up Untappd from a config entry."""
    client = UntappdClient(
        async_get_clientsession(hass), entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    )
    coordinator = UntappdDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: UntappdConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
