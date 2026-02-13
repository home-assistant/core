"""The Homevolt integration."""

from __future__ import annotations

from homevolt import Homevolt

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Set up Homevolt from a config entry."""
    host: str = entry.data[CONF_HOST]
    password: str | None = entry.data.get(CONF_PASSWORD)

    websession = async_get_clientsession(hass)
    client = Homevolt(host, password, websession=websession)

    coordinator = HomevoltDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.client.close_connection()

    return unload_ok
