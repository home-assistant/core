"""Koito integration lifecycle."""

from aiokoito import KoitoApi

from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import KoitoConfigEntry, KoitoCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: KoitoConfigEntry) -> None:
    """Set up Koito from a config entry."""
    api = KoitoApi(
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        async_get_clientsession(hass),
    )
    coordinator = KoitoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: KoitoConfigEntry) -> None:
    """Unload platform and discard its coordinator."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
