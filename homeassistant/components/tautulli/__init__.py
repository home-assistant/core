"""The Tautulli integration."""

from pytautulli import PyTautulli, PyTautulliHostConfiguration

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import TautulliConfigEntry, TautulliDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TautulliConfigEntry) -> None:
    """Set up Tautulli from a config entry."""
    host_configuration = PyTautulliHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        url=entry.data[CONF_URL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    api_client = PyTautulli(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    entry.runtime_data = TautulliDataUpdateCoordinator(
        hass, entry, host_configuration, api_client
    )
    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TautulliConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
