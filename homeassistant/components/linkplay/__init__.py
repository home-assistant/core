"""Support for LinkPlay devices."""

from dataclasses import dataclass

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge
from linkplay.controller import LinkPlayController
from linkplay.discovery import linkplay_factory_httpapi_bridge
from linkplay.exceptions import LinkPlayRequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS, SHARED_DATA, LinkPlaySharedData
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

    # try create a bridge
    try:
        bridge = await linkplay_factory_httpapi_bridge(entry.data[CONF_HOST], session)
    except LinkPlayRequestException as exception:
        raise ConfigEntryNotReady(
            f"Failed to connect to LinkPlay device at {entry.data[CONF_HOST]}"
        ) from exception

    # setup the controller and discover multirooms
    controller: LinkPlayController | None = None
    hass.data.setdefault(DOMAIN, {})
    if SHARED_DATA not in hass.data[DOMAIN]:
        controller = LinkPlayController(session)
        hass.data[DOMAIN][SHARED_DATA] = LinkPlaySharedData(controller, {})
    else:
        controller = hass.data[DOMAIN][SHARED_DATA].controller

    await controller.add_bridge(bridge)
    await controller.discover_multirooms()

    # forward to platforms
    entry.runtime_data = LinkPlayData(bridge=bridge)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Unload a config entry."""

    # remove the bridge from the controller and discover multirooms
    bridge: LinkPlayBridge | None = entry.runtime_data.bridge
    controller: LinkPlayController = hass.data[DOMAIN][SHARED_DATA].controller
    await controller.remove_bridge(bridge)
    await controller.discover_multirooms()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
