"""Denon HEOS Media Player."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.media_player.const import (
    DOMAIN as MEDIA_PLAYER_DOMAIN)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import Throttle

from .config_flow import format_title
from .const import (
    COMMAND_RETRY_ATTEMPTS, COMMAND_RETRY_DELAY, DATA_CONTROLLER,
    DATA_SOURCE_MANAGER, DOMAIN, SIGNAL_HEOS_SOURCES_UPDATED)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

MIN_UPDATE_SOURCES = timedelta(seconds=1)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the HEOS component."""
    if DOMAIN not in config:
        return True
    host = config[DOMAIN][CONF_HOST]
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        # Create new entry based on config
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={'source': 'import'},
                data={CONF_HOST: host}))
    else:
        # Check if host needs to be updated
        entry = entries[0]
        if entry.data[CONF_HOST] != host:
            entry.data[CONF_HOST] = host
            entry.title = format_title(host)
            hass.config_entries.async_update_entry(entry)

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Initialize config entry which represents the HEOS controller."""
    from pyheos import Heos, CommandError
    host = entry.data[CONF_HOST]
    # Setting all_progress_events=False ensures that we only receive a
    # media position update upon start of playback or when media changes
    controller = Heos(host, all_progress_events=False)
    try:
        await controller.connect(auto_reconnect=True)
    # Auto reconnect only operates if initial connection was successful.
    except (asyncio.TimeoutError, ConnectionError, CommandError) as error:
        await controller.disconnect()
        _LOGGER.debug("Unable to connect to controller %s: %s", host, error)
        raise ConfigEntryNotReady

    # Disconnect when shutting down
    async def disconnect_controller(event):
        await controller.disconnect()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_controller)

    # Get players and sources
    try:
        players = await controller.get_players()
        favorites = {}
        if controller.is_signed_in:
            favorites = await controller.get_favorites()
        else:
            _LOGGER.warning("%s is not logged in to your HEOS account and will"
                            " be unable to retrieve your favorites", host)
        inputs = await controller.get_input_sources()
    except (asyncio.TimeoutError, ConnectionError, CommandError) as error:
        await controller.disconnect()
        _LOGGER.debug("Unable to retrieve players and sources: %s", error,
                      exc_info=isinstance(error, CommandError))
        raise ConfigEntryNotReady

    source_manager = SourceManager(favorites, inputs)
    source_manager.connect_update(hass, controller)

    hass.data[DOMAIN] = {
        DATA_CONTROLLER: controller,
        DATA_SOURCE_MANAGER: source_manager,
        MEDIA_PLAYER_DOMAIN: players
    }
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, MEDIA_PLAYER_DOMAIN))
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER]
    controller.dispatcher.disconnect_all()
    await controller.disconnect()
    hass.data.pop(DOMAIN)
    return await hass.config_entries.async_forward_entry_unload(
        entry, MEDIA_PLAYER_DOMAIN)


class SourceManager:
    """Class that manages sources for players."""

    def __init__(self, favorites, inputs, *,
                 retry_delay: int = COMMAND_RETRY_DELAY,
                 max_retry_attempts: int = COMMAND_RETRY_ATTEMPTS):
        """Init input manager."""
        self.retry_delay = retry_delay
        self.max_retry_attempts = max_retry_attempts
        self.favorites = favorites
        self.inputs = inputs
        self.source_list = self._build_source_list()

    def _build_source_list(self):
        """Build a single list of inputs from various types."""
        source_list = []
        source_list.extend([favorite.name for favorite
                            in self.favorites.values()])
        source_list.extend([source.name for source in self.inputs])
        return source_list

    async def play_source(self, source: str, player):
        """Determine type of source and play it."""
        index = next((index for index, favorite in self.favorites.items()
                      if favorite.name == source), None)
        if index is not None:
            await player.play_favorite(index)
            return

        input_source = next((input_source for input_source in self.inputs
                             if input_source.name == source), None)
        if input_source is not None:
            await player.play_input_source(input_source)
            return

        _LOGGER.error("Unknown source: %s", source)

    def get_current_source(self, now_playing_media):
        """Determine current source from now playing media."""
        from pyheos import const
        # Match input by input_name:media_id
        if now_playing_media.source_id == const.MUSIC_SOURCE_AUX_INPUT:
            return next((input_source.name for input_source in self.inputs
                         if input_source.input_name ==
                         now_playing_media.media_id), None)
        # Try matching favorite by name:station or media_id:album_id
        return next((source.name for source in self.favorites.values()
                     if source.name == now_playing_media.station
                     or source.media_id == now_playing_media.album_id), None)

    def connect_update(self, hass, controller):
        """
        Connect listener for when sources change and signal player update.

        EVENT_SOURCES_CHANGED is often raised multiple times in response to a
        physical event therefore throttle it. Retrieving sources immediately
        after the event may fail so retry.
        """
        from pyheos import CommandError, const

        @Throttle(MIN_UPDATE_SOURCES)
        async def get_sources():
            retry_attempts = 0
            while True:
                try:
                    favorites = {}
                    if controller.is_signed_in:
                        favorites = await controller.get_favorites()
                    inputs = await controller.get_input_sources()
                    return favorites, inputs
                except (asyncio.TimeoutError, ConnectionError, CommandError) \
                        as error:
                    if retry_attempts < self.max_retry_attempts:
                        retry_attempts += 1
                        _LOGGER.debug("Error retrieving sources and will "
                                      "retry: %s", error,
                                      exc_info=isinstance(error, CommandError))
                        await asyncio.sleep(self.retry_delay)
                    else:
                        _LOGGER.error("Unable to update sources: %s", error,
                                      exc_info=isinstance(error, CommandError))
                        return

        async def update_sources(event, data):
            if event in (const.EVENT_SOURCES_CHANGED,
                         const.EVENT_USER_CHANGED):
                sources = await get_sources()
                # If throttled, it will return None
                if sources:
                    self.favorites, self.inputs = sources
                    self.source_list = self._build_source_list()
                    _LOGGER.debug("Sources updated due to changed event")
                    # Let players know to update
                    hass.helpers.dispatcher.async_dispatcher_send(
                        SIGNAL_HEOS_SOURCES_UPDATED)

        controller.dispatcher.connect(
            const.SIGNAL_CONTROLLER_EVENT, update_sources)
