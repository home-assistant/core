"""The Bang & Olufsen integration."""

from __future__ import annotations

from dataclasses import dataclass

from aiohttp.client_exceptions import (
    ClientConnectorError,
    ClientOSError,
    ServerTimeoutError,
)
from mozart_api.exceptions import ApiException
from mozart_api.mozart_client import MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN
from .websocket import BangOlufsenWebsocket


@dataclass
class BangOlufsenData:
    """Dataclass for API client and WebSocket client."""

    websocket: BangOlufsenWebsocket
    client: MozartClient


PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # Remove casts to str
    assert entry.unique_id

    # Create device now as BangOlufsenWebsocket needs a device for debug logging, firing events etc.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        name=entry.title,
        model=entry.data[CONF_MODEL],
    )

    client = MozartClient(host=entry.data[CONF_HOST])

    # Check API and WebSocket connection
    try:
        await client.check_device_connection(True)
    except* (
        ClientConnectorError,
        ClientOSError,
        ServerTimeoutError,
        ApiException,
        TimeoutError,
    ) as error:
        await client.close_api_client()
        raise ConfigEntryNotReady(f"Unable to connect to {entry.title}") from error

    websocket = BangOlufsenWebsocket(hass, entry, client)

    # Add the websocket and API client
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BangOlufsenData(
        websocket,
        client,
    )

    # Start WebSocket connection
    await client.connect_notifications(remote_control=True, reconnect=True)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Close the API client and WebSocket notification listener
    hass.data[DOMAIN][entry.entry_id].client.disconnect_notifications()
    await hass.data[DOMAIN][entry.entry_id].client.close_api_client()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
