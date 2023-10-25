"""The Bang & Olufsen integration."""
from __future__ import annotations

import logging
from multiprocessing.pool import ApplyResult
from typing import cast

from mozart_api.exceptions import ServiceException
from mozart_api.models import BatteryState
from mozart_api.mozart_client import MozartClient
from urllib3.exceptions import MaxRetryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, ENTITY_ENUM, WEBSOCKET_CONNECTION_DELAY
from .media_player import BangOlufsenMediaPlayer
from .websocket import BangOlufsenWebsocket

PLATFORMS = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Ensure that a unique id is available
    if not entry.unique_id:
        raise ConfigEntryError("Can't retrieve unique id from config entry. Aborting")

    # If connection can't be made abort.
    if not await init_entities(hass, entry):
        raise ConfigEntryNotReady(f"Unable to connect to {entry.title}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def init_entities(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise the supported entities of the device."""
    client = MozartClient(
        host=entry.data[CONF_HOST], urllib3_logging_level=logging.ERROR
    )

    # Check connection and try to initialize it.
    try:
        cast(
            ApplyResult[BatteryState],
            client.get_battery_state(async_req=True, _request_timeout=3),
        ).get()
    except (MaxRetryError, ServiceException):
        _LOGGER.error("Unable to connect to %s", entry.data[CONF_NAME])
        return False

    websocket = BangOlufsenWebsocket(hass, entry)

    # Create the Media Player entity.
    media_player = BangOlufsenMediaPlayer(entry)

    # Add the created entities
    hass.data[DOMAIN][entry.unique_id] = {
        ENTITY_ENUM.WEBSOCKET: websocket,
        ENTITY_ENUM.MEDIA_PLAYER: media_player,
    }

    # Start the WebSocket listener with a delay to allow for entity and dispatcher listener creation
    async_call_later(hass, WEBSOCKET_CONNECTION_DELAY, websocket.connect_websocket)

    return True
