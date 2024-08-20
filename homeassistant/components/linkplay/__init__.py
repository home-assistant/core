"""Support for LinkPlay devices."""

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge
from linkplay.discovery import linkplay_factory_httpapi_bridge
from linkplay.utils import async_create_unverified_client_session

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import DATA_SESSION, DOMAIN, PLATFORMS


class LinkPlayIntegrationData:
    """Data for LinkPlay integration."""

    session: ClientSession


class LinkPlayData:
    """Data for LinkPlay."""

    bridge: LinkPlayBridge


type LinkPlayConfigEntry = ConfigEntry[LinkPlayData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LinkPlay component."""
    hass.data[DOMAIN] = {}

    session = await async_create_unverified_client_session()
    hass.data[DOMAIN][DATA_SESSION] = session
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Async setup hass config entry. Called when an entry has been setup."""

    session: ClientSession = hass.data[DOMAIN][DATA_SESSION]
    if (
        bridge := await linkplay_factory_httpapi_bridge(entry.data[CONF_HOST], session)
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
