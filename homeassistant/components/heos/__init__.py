"""Denon HEOS Media Player."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pyheos import Heos, HeosError, const as heos_const
import voluptuous as vol

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import services
from .config_flow import format_title
from .const import (
    COMMAND_RETRY_ATTEMPTS,
    COMMAND_RETRY_DELAY,
    DATA_CONTROLLER_MANAGER,
    DATA_SOURCE_MANAGER,
    DOMAIN,
    SIGNAL_HEOS_UPDATED,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_HOST): cv.string})}, extra=vol.ALLOW_EXTRA
)

MIN_UPDATE_SOURCES = timedelta(seconds=1)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the HEOS component."""
    if DOMAIN not in config:
        return True
    host = config[DOMAIN][CONF_HOST]
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        # Create new entry based on config
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: host}
            )
        )
    else:
        # Check if host needs to be updated
        entry = entries[0]
        if entry.data[CONF_HOST] != host:
            hass.config_entries.async_update_entry(
                entry, title=format_title(host), data={**entry.data, CONF_HOST: host}
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Initialize config entry which represents the HEOS controller."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    host = entry.data[CONF_HOST]
    # Setting all_progress_events=False ensures that we only receive a
    # media position update upon start of playback or when media changes
    controller = Heos(host, all_progress_events=False)
    try:
        await controller.connect(auto_reconnect=True)
    # Auto reconnect only operates if initial connection was successful.
    except HeosError as error:
        await controller.disconnect()
        _LOGGER.debug("Unable to connect to controller %s: %s", host, error)
        raise ConfigEntryNotReady from error

    # Disconnect when shutting down
    async def disconnect_controller(event):
        await controller.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_controller)
    )

    # Get players and sources
    try:
        players = await controller.get_players()
        favorites = {}
        if controller.is_signed_in:
            favorites = await controller.get_favorites()
        else:
            _LOGGER.warning(
                "%s is not logged in to a HEOS account and will be unable to retrieve "
                "HEOS favorites: Use the 'heos.sign_in' service to sign-in to a HEOS account",
                host,
            )
        inputs = await controller.get_input_sources()
    except HeosError as error:
        await controller.disconnect()
        _LOGGER.debug("Unable to retrieve players and sources: %s", error)
        raise ConfigEntryNotReady from error

    controller_manager = ControllerManager(hass, controller)
    await controller_manager.connect_listeners()

    source_manager = SourceManager(favorites, inputs)
    source_manager.connect_update(hass, controller)

    hass.data[DOMAIN] = {
        DATA_CONTROLLER_MANAGER: controller_manager,
        DATA_SOURCE_MANAGER: source_manager,
        MEDIA_PLAYER_DOMAIN: players,
    }

    services.register(hass, controller)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MEDIA_PLAYER_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    controller_manager = hass.data[DOMAIN][DATA_CONTROLLER_MANAGER]
    await controller_manager.disconnect()
    hass.data.pop(DOMAIN)

    services.remove(hass)

    return await hass.config_entries.async_forward_entry_unload(
        entry, MEDIA_PLAYER_DOMAIN
    )


class ControllerManager:
    """Class that manages events of the controller."""

    def __init__(self, hass, controller):
        """Init the controller manager."""
        self._hass = hass
        self._device_registry = None
        self._entity_registry = None
        self.controller = controller
        self._signals = []

    async def connect_listeners(self):
        """Subscribe to events of interest."""
        self._device_registry, self._entity_registry = await asyncio.gather(
            self._hass.helpers.device_registry.async_get_registry(),
            self._hass.helpers.entity_registry.async_get_registry(),
        )
        # Handle controller events
        self._signals.append(
            self.controller.dispatcher.connect(
                heos_const.SIGNAL_CONTROLLER_EVENT, self._controller_event
            )
        )
        # Handle connection-related events
        self._signals.append(
            self.controller.dispatcher.connect(
                heos_const.SIGNAL_HEOS_EVENT, self._heos_event
            )
        )

    async def disconnect(self):
        """Disconnect subscriptions."""
        for signal_remove in self._signals:
            signal_remove()
        self._signals.clear()
        self.controller.dispatcher.disconnect_all()
        await self.controller.disconnect()

    async def _controller_event(self, event, data):
        """Handle controller event."""
        if event == heos_const.EVENT_PLAYERS_CHANGED:
            self.update_ids(data[heos_const.DATA_MAPPED_IDS])
        # Update players
        self._hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_HEOS_UPDATED)

    async def _heos_event(self, event):
        """Handle connection event."""
        if event == heos_const.EVENT_CONNECTED:
            try:
                # Retrieve latest players and refresh status
                data = await self.controller.load_players()
                self.update_ids(data[heos_const.DATA_MAPPED_IDS])
            except HeosError as ex:
                _LOGGER.error("Unable to refresh players: %s", ex)
        # Update players
        self._hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_HEOS_UPDATED)

    def update_ids(self, mapped_ids: dict[int, int]):
        """Update the IDs in the device and entity registry."""
        # mapped_ids contains the mapped IDs (new:old)
        for new_id, old_id in mapped_ids.items():
            # update device registry
            entry = self._device_registry.async_get_device({(DOMAIN, old_id)})
            new_identifiers = {(DOMAIN, new_id)}
            if entry:
                self._device_registry.async_update_device(
                    entry.id, new_identifiers=new_identifiers
                )
                _LOGGER.debug(
                    "Updated device %s identifiers to %s", entry.id, new_identifiers
                )
            # update entity registry
            entity_id = self._entity_registry.async_get_entity_id(
                MEDIA_PLAYER_DOMAIN, DOMAIN, str(old_id)
            )
            if entity_id:
                self._entity_registry.async_update_entity(
                    entity_id, new_unique_id=str(new_id)
                )
                _LOGGER.debug("Updated entity %s unique id to %s", entity_id, new_id)


class SourceManager:
    """Class that manages sources for players."""

    def __init__(
        self,
        favorites,
        inputs,
        *,
        retry_delay: int = COMMAND_RETRY_DELAY,
        max_retry_attempts: int = COMMAND_RETRY_ATTEMPTS,
    ):
        """Init input manager."""
        self.retry_delay = retry_delay
        self.max_retry_attempts = max_retry_attempts
        self.favorites = favorites
        self.inputs = inputs
        self.source_list = self._build_source_list()

    def _build_source_list(self):
        """Build a single list of inputs from various types."""
        source_list = []
        source_list.extend([favorite.name for favorite in self.favorites.values()])
        source_list.extend([source.name for source in self.inputs])
        return source_list

    async def play_source(self, source: str, player):
        """Determine type of source and play it."""
        index = next(
            (
                index
                for index, favorite in self.favorites.items()
                if favorite.name == source
            ),
            None,
        )
        if index is not None:
            await player.play_favorite(index)
            return

        input_source = next(
            (
                input_source
                for input_source in self.inputs
                if input_source.name == source
            ),
            None,
        )
        if input_source is not None:
            await player.play_input_source(input_source)
            return

        _LOGGER.error("Unknown source: %s", source)

    def get_current_source(self, now_playing_media):
        """Determine current source from now playing media."""
        # Match input by input_name:media_id
        if now_playing_media.source_id == heos_const.MUSIC_SOURCE_AUX_INPUT:
            return next(
                (
                    input_source.name
                    for input_source in self.inputs
                    if input_source.input_name == now_playing_media.media_id
                ),
                None,
            )
        # Try matching favorite by name:station or media_id:album_id
        return next(
            (
                source.name
                for source in self.favorites.values()
                if source.name == now_playing_media.station
                or source.media_id == now_playing_media.album_id
            ),
            None,
        )

    def connect_update(self, hass, controller):
        """
        Connect listener for when sources change and signal player update.

        EVENT_SOURCES_CHANGED is often raised multiple times in response to a
        physical event therefore throttle it. Retrieving sources immediately
        after the event may fail so retry.
        """

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
                except HeosError as error:
                    if retry_attempts < self.max_retry_attempts:
                        retry_attempts += 1
                        _LOGGER.debug(
                            "Error retrieving sources and will retry: %s", error
                        )
                        await asyncio.sleep(self.retry_delay)
                    else:
                        _LOGGER.error("Unable to update sources: %s", error)
                        return

        async def update_sources(event, data=None):
            if event in (
                heos_const.EVENT_SOURCES_CHANGED,
                heos_const.EVENT_USER_CHANGED,
                heos_const.EVENT_CONNECTED,
            ):
                sources = await get_sources()
                # If throttled, it will return None
                if sources:
                    self.favorites, self.inputs = sources
                    self.source_list = self._build_source_list()
                    _LOGGER.debug("Sources updated due to changed event")
                    # Let players know to update
                    hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_HEOS_UPDATED)

        controller.dispatcher.connect(
            heos_const.SIGNAL_CONTROLLER_EVENT, update_sources
        )
        controller.dispatcher.connect(heos_const.SIGNAL_HEOS_EVENT, update_sources)
