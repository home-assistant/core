"""The AirLino integration."""

from airlino_api import AirlinoApi

from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import AirlinoConfigEntry, AirlinoDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: AirlinoConfigEntry) -> None:
    """Set up AirLino from a config entry."""
    api = AirlinoApi(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        api_version=entry.data[CONF_API_VERSION],
        session=async_get_clientsession(hass),
    )

    coordinator = AirlinoDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AirlinoConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
