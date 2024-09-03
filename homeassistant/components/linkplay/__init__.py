"""Support for LinkPlay devices."""

from dataclasses import dataclass

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge
from linkplay.discovery import linkplay_factory_httpapi_bridge
from linkplay.exceptions import LinkPlayRequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .utils import async_get_client_session


@dataclass
class LinkPlayData:
    """Data for LinkPlay."""

    bridge: LinkPlayBridge


type LinkPlayConfigEntry = ConfigEntry[LinkPlayData]


async def async_setup_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Async setup hass config entry. Called when an entry has been setup."""

    session: ClientSession = await async_get_client_session(hass)
    bridge: LinkPlayBridge | None = None

    try:
        bridge = await linkplay_factory_httpapi_bridge(entry.data[CONF_HOST], session)
    except LinkPlayRequestException as exception:
        raise ConfigEntryNotReady(
            f"Failed to connect to LinkPlay device at {entry.data[CONF_HOST]}"
        ) from exception

    entry.runtime_data = LinkPlayData(bridge=bridge)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
