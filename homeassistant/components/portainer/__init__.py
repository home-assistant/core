"""The Portainer integration."""

from __future__ import annotations

from aiohttp import CookieJar
from pyportainer import Portainer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import PortainerCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

type PortainerConfigEntry = ConfigEntry[PortainerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Set up Portainer from a config entry."""

    session = async_create_clientsession(
        hass,
        entry.data[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    client = Portainer(
        api_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_ACCESS_TOKEN],
        session=session,
    )

    coordinator = PortainerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
