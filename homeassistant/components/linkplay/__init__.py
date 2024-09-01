"""Support for LinkPlay devices."""

from linkplay.bridge import LinkPlayBridge
from linkplay.discovery import linkplay_factory_bridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS


class LinkPlayData:
    """Data for LinkPlay."""

    bridge: LinkPlayBridge


type LinkPlayConfigEntry = ConfigEntry[LinkPlayData]


async def async_setup_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Async setup hass config entry. Called when an entry has been setup."""

    session = async_get_clientsession(hass)
    if (
        bridge := await linkplay_factory_bridge(entry.data[CONF_HOST], session)
    ) is None:
        raise ConfigEntryNotReady(
            f"Failed to connect to LinkPlay device at {entry.data[CONF_HOST]}"
        )

    entry.runtime_data = LinkPlayData()
    entry.runtime_data.bridge = bridge
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
