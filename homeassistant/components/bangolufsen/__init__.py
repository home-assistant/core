"""The Bang & Olufsen integration."""
from __future__ import annotations

import logging

from mozart_api.mozart_client import MozartClient
from urllib3.exceptions import MaxRetryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, EntityEnum
from .media_player import BangOlufsenMediaPlayer
from .websocket import BangOlufsenWebsocket

PLATFORMS = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Check if there are available options.
    if entry.options:
        entry.data = entry.options

    # If connection can't be made abort.
    if not await init_entities(hass, entry):
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def init_entities(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise the supported entities of the device."""
    client = MozartClient(host=entry.data[CONF_HOST])

    # Check connection and try to initialize it.
    try:
        client.get_battery_state(async_req=True, _request_timeout=3).get()
    except MaxRetryError:
        _LOGGER.error("Unable to connect to %s", entry.data[CONF_NAME])
        return False

    websocket = BangOlufsenWebsocket(hass, entry)

    # Create the Media Player entity.
    media_player = BangOlufsenMediaPlayer(entry)

    # Add the created entities
    hass.data[DOMAIN][entry.unique_id] = {
        EntityEnum.WEBSOCKET: websocket,
        EntityEnum.MEDIA_PLAYER: media_player,
    }

    # Start the WebSocket listener with a delay to allow for entity and dispatcher listener creation
    async_call_later(hass, 3.0, websocket.connect_websocket)

    return True
