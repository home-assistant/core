"""Support for LinkPlay devices."""

from dataclasses import dataclass
import logging

from linkplay.bridge import LinkPlayBridge
from linkplay.discovery import linkplay_factory_bridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]


@dataclass
class LinkPlayData:
    """Data for LinkPlay."""

    bridge: LinkPlayBridge


type LinkPlayConfigEntry = ConfigEntry[LinkPlayData]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Async setup hass config entry. Called when an entry has been setup."""

    session = async_get_clientsession(hass)
    if (
        bridge := await linkplay_factory_bridge(entry.data[CONF_HOST], session)
    ) is None:
        _LOGGER.error(
            "Failed to connect to LinkPlay device at %s", entry.data[CONF_HOST]
        )
        raise ConfigEntryNotReady

    entry.runtime_data = LinkPlayData(bridge=bridge)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
