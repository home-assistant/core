"""The Bang & Olufsen integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp.client_exceptions import ClientConnectorError
from mozart_api.mozart_client import MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .websocket import BangOlufsenWebsocket

PLATFORMS = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)


@dataclass
class BangOlufsenData:
    """Dataclass for storing entities."""

    websocket: BangOlufsenWebsocket


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    client = MozartClient(
        host=entry.data[CONF_HOST], urllib3_logging_level=logging.DEBUG
    )

    # Check connection and try to initialize it.
    async with client:
        try:
            await client.get_battery_state(_request_timeout=3)
        except (TimeoutError, ClientConnectorError, Exception) as error:
            raise ConfigEntryNotReady(f"Unable to connect to {entry.title}") from error

    websocket = BangOlufsenWebsocket(hass, entry)

    # Add the websocket
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BangOlufsenData(websocket)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    websocket.connect_websocket()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
