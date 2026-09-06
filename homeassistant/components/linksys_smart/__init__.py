"""The Linksys Smart Wi-Fi integration."""

from jnap import JNAPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import LinksysDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

type LinksysConfigEntry = ConfigEntry[LinksysDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LinksysConfigEntry) -> bool:
    """Set up Linksys from a config entry."""
    kwargs: dict[str, str] = {}
    if username := entry.data.get(CONF_USERNAME):
        kwargs["username"] = username
    client = JNAPClient(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
        entry.data[CONF_PASSWORD],
        **kwargs,
    )
    coordinator = LinksysDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinksysConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
