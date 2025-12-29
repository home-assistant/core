"""The Bang & Olufsen integration."""

from __future__ import annotations

from dataclasses import dataclass

from aiohttp.client_exceptions import (
    ClientConnectorError,
    ClientOSError,
    ServerTimeoutError,
    WSMessageTypeError,
)
from mozart_api.exceptions import ApiException
from mozart_api.mozart_client import MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.util.ssl import get_default_context

from .const import DOMAIN
from .websocket import BeoWebsocket


@dataclass
class BeoData:
    """Dataclass for API client and WebSocket client."""

    websocket: BeoWebsocket
    client: MozartClient


type BeoConfigEntry = ConfigEntry[BeoData]

PLATFORMS = [Platform.EVENT, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: BeoConfigEntry) -> bool:
    """Set up from a config entry."""

    # Remove casts to str
    assert entry.unique_id

    # Create device now as BeoWebsocket needs a device for debug logging, firing events etc.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        name=entry.title,
        model=entry.data[CONF_MODEL],
    )

    client = MozartClient(host=entry.data[CONF_HOST], ssl_context=get_default_context())

    # Check API and WebSocket connection
    try:
        await client.check_device_connection(True)
    except* (
        ClientConnectorError,
        ClientOSError,
        ServerTimeoutError,
        ApiException,
        TimeoutError,
        WSMessageTypeError,
    ) as error:
        await client.close_api_client()
        raise ConfigEntryNotReady(f"Unable to connect to {entry.title}") from error

    websocket = BeoWebsocket(hass, entry, client)

    # Add the websocket and API client
    entry.runtime_data = BeoData(websocket, client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start WebSocket connection once the platforms have been loaded.
    # This ensures that the initial WebSocket notifications are dispatched to entities
    await client.connect_notifications(remote_control=True, reconnect=True)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeoConfigEntry) -> bool:
    """Unload a config entry."""
    # Close the API client and WebSocket notification listener
    entry.runtime_data.client.disconnect_notifications()
    await entry.runtime_data.client.close_api_client()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
