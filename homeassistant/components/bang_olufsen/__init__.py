"""The Bang & Olufsen integration."""
from __future__ import annotations

from dataclasses import dataclass

from aiohttp.client_exceptions import ClientConnectorError
from mozart_api.exceptions import ApiException
from mozart_api.mozart_client import MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

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

    client = MozartClient(host=entry.data[CONF_HOST], websocket_reconnect=True)

    # Check connection and try to initialize it.
    try:
        await client.get_battery_state(_request_timeout=3)
    except (ApiException, ClientConnectorError, TimeoutError) as error:
        await client.close_api_client()
        raise ConfigEntryNotReady(f"Unable to connect to {entry.title}") from error

    websocket = BangOlufsenWebsocket(hass, entry, client)

    # Add the websocket
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BangOlufsenData(
        websocket,
        client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    client.connect_notifications()

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
