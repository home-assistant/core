"""The NEPViewer integration."""

from aionepviewer import NepViewer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import NepViewerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type NepViewerConfigEntry = ConfigEntry[NepViewerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NepViewerConfigEntry) -> bool:
    """Set up NEPViewer from a config entry."""
    client = NepViewer(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = NepViewerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NepViewerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
