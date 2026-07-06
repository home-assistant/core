"""Xthings Cloud integration for Home Assistant."""

from ha_xthings_cloud import XthingsCloudApiClient

from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import XthingsCloudConfigEntry, XthingsCloudCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> bool:
    """Set up config entry."""
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])

    coordinator = XthingsCloudCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_websocket()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> bool:
    """Unload config entry."""
    coordinator = entry.runtime_data
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await coordinator.async_stop_websocket()
    return unload_ok
