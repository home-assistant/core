"""Denon HEOS Media Player."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pyheos import Heos, HeosError, const as heos_const
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import services
from .config_flow import format_title
from .const import (
    COMMAND_RETRY_ATTEMPTS,
    COMMAND_RETRY_DELAY,
    DATA_CONTROLLER_MANAGER,
    DATA_ENTITY_ID_MAP,
    DATA_GROUP_MANAGER,
    DATA_SOURCE_MANAGER,
    DOMAIN,
    SIGNAL_HEOS_PLAYER_ADDED,
    SIGNAL_HEOS_UPDATED,
)

PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: vol.Schema({vol.Required(CONF_HOST): cv.string})},
    ),
    extra=vol.ALLOW_EXTRA,
)

MIN_UPDATE_SOURCES = timedelta(seconds=1)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
                (
                    "%s is not logged in to a HEOS account and will be unable to"
                    " retrieve HEOS favorites: Use the 'heos.sign_in' service to"
                    " sign-in to a HEOS account"
                ),
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

    group_manager = GroupManager(hass, controller)

    hass.data[DOMAIN] = {
        DATA_CONTROLLER_MANAGER: controller_manager,
        DATA_GROUP_MANAGER: group_manager,
        DATA_SOURCE_MANAGER: source_manager,
        Platform.MEDIA_PLAYER: players,
        # Maps player_id to entity_id. Populated by the individual
        # HeosMediaPlayer entities.
        DATA_ENTITY_ID_MAP: {},
    }

    services.register(hass, controller)
    group_manager.connect_update()
    entry.async_on_unload(group_manager.disconnect_update)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller_manager = hass.data[DOMAIN][DATA_CONTROLLER_MANAGER]
    await controller_manager.disconnect()
    hass.data.pop(DOMAIN)

    services.remove(hass)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
        self._device_registry = dr.async_get(self._hass)
        self._entity_registry = er.async_get(self._hass)

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
        async_dispatcher_send(self._hass, SIGNAL_HEOS_UPDATED)

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
        async_dispatcher_send(self._hass, SIGNAL_HEOS_UPDATED)

    def update_ids(self, mapped_ids: dict[int, int]):
        """Update the IDs in the device and entity registry."""
        # mapped_ids contains the mapped IDs (new:old)
        for new_id, old_id in mapped_ids.items():
            # update device registry
            entry = self._device_registry.async_get_device(
                identifiers={(DOMAIN, old_id)}
            )
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
                Platform.MEDIA_PLAYER, DOMAIN, str(old_id)
            )
            if entity_id:
                self._entity_registry.async_update_entity(
                    entity_id, new_unique_id=str(new_id)
                )
                _LOGGER.debug("Updated entity %s unique id to %s", entity_id, new_id)


class GroupManager:
    """Class that manages HEOS groups."""

    def __init__(self, hass, controller):
        """Init group manager."""
        self._hass = hass
        self._group_membership = {}
        self._disconnect_player_added = None
        self._initialized = False
        self.controller = controller

    def _get_entity_id_to_player_id_map(self) -> dict:
        """Return mapping of all HeosMediaPlayer entity_ids to player_ids."""
        return {v: k for k, v in self._hass.data[DOMAIN][DATA_ENTITY_ID_MAP].items()}

    async def async_get_group_membership(self):
        """Return all group members for each player as entity_ids."""
        group_info_by_entity_id = {
            player_entity_id: []
            for player_entity_id in self._get_entity_id_to_player_id_map()
        }

        try:
            groups = await self.controller.get_groups(refresh=True)
        except HeosError as err:
            _LOGGER.error("Unable to get HEOS group info: %s", err)
            return group_info_by_entity_id

        player_id_to_entity_id_map = self._hass.data[DOMAIN][DATA_ENTITY_ID_MAP]
        for group in groups.values():
            leader_entity_id = player_id_to_entity_id_map.get(group.leader.player_id)
            member_entity_ids = [
                player_id_to_entity_id_map[member.player_id]
                for member in group.members
                if member.player_id in player_id_to_entity_id_map
            ]
            # Make sure the group leader is always the first element
            group_info = [leader_entity_id, *member_entity_ids]
            if leader_entity_id:
                group_info_by_entity_id[leader_entity_id] = group_info
                for member_entity_id in member_entity_ids:
                    group_info_by_entity_id[member_entity_id] = group_info

        return group_info_by_entity_id

    async def async_join_players(
        self, leader_entity_id: str, member_entity_ids: list[str]
    ) -> None:
        """Create a group a group leader and member players."""
        entity_id_to_player_id_map = self._get_entity_id_to_player_id_map()
        leader_id = entity_id_to_player_id_map.get(leader_entity_id)
        if not leader_id:
            raise HomeAssistantError(
                f"The group leader {leader_entity_id} could not be resolved to a HEOS"
                " player."
            )
        member_ids = [
            entity_id_to_player_id_map[member]
            for member in member_entity_ids
            if member in entity_id_to_player_id_map
        ]

        try:
            await self.controller.create_group(leader_id, member_ids)
        except HeosError as err:
            _LOGGER.error(
                "Failed to group %s with %s: %s",
                leader_entity_id,
                member_entity_ids,
                err,
            )

    async def async_unjoin_player(self, player_entity_id: str):
        """Remove `player_entity_id` from any group."""
        player_id = self._get_entity_id_to_player_id_map().get(player_entity_id)
        if not player_id:
            raise HomeAssistantError(
                f"The player {player_entity_id} could not be resolved to a HEOS player."
            )

        try:
            await self.controller.create_group(player_id, [])
        except HeosError as err:
            _LOGGER.error(
                "Failed to ungroup %s: %s",
                player_entity_id,
                err,
            )

    async def async_update_groups(self, event, data=None):
        """Update the group membership from the controller."""
        if event in (
            heos_const.EVENT_GROUPS_CHANGED,
            heos_const.EVENT_CONNECTED,
            SIGNAL_HEOS_PLAYER_ADDED,
        ):
            if groups := await self.async_get_group_membership():
                self._group_membership = groups
                _LOGGER.debug("Groups updated due to change event")
                # Let players know to update
                async_dispatcher_send(self._hass, SIGNAL_HEOS_UPDATED)
            else:
                _LOGGER.debug("Groups empty")

    def connect_update(self):
        """Connect listener for when groups change and signal player update."""
        self.controller.dispatcher.connect(
            heos_const.SIGNAL_CONTROLLER_EVENT, self.async_update_groups
        )
        self.controller.dispatcher.connect(
            heos_const.SIGNAL_HEOS_EVENT, self.async_update_groups
        )

        # When adding a new HEOS player we need to update the groups.
        async def _async_handle_player_added():
            # Avoid calling async_update_groups when `DATA_ENTITY_ID_MAP` has not been
            # fully populated yet. This may only happen during early startup.
            if (
                len(self._hass.data[DOMAIN][Platform.MEDIA_PLAYER])
                <= len(self._hass.data[DOMAIN][DATA_ENTITY_ID_MAP])
                and not self._initialized
            ):
                self._initialized = True
                await self.async_update_groups(SIGNAL_HEOS_PLAYER_ADDED)

        self._disconnect_player_added = async_dispatcher_connect(
            self._hass, SIGNAL_HEOS_PLAYER_ADDED, _async_handle_player_added
        )

    @callback
    def disconnect_update(self):
        """Disconnect the listeners."""
        if self._disconnect_player_added:
            self._disconnect_player_added()
            self._disconnect_player_added = None

    @property
    def group_membership(self):
        """Provide access to group members for player entities."""
        return self._group_membership


class SourceManager:
    """Class that manages sources for players."""

    def __init__(
        self,
        favorites,
        inputs,
        *,
        retry_delay: int = COMMAND_RETRY_DELAY,
        max_retry_attempts: int = COMMAND_RETRY_ATTEMPTS,
    ) -> None:
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
        """Connect listener for when sources change and signal player update.

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
                # If throttled, it will return None
                if sources := await get_sources():
                    self.favorites, self.inputs = sources
                    self.source_list = self._build_source_list()
                    _LOGGER.debug("Sources updated due to changed event")
                    # Let players know to update
                    async_dispatcher_send(hass, SIGNAL_HEOS_UPDATED)

        controller.dispatcher.connect(
            heos_const.SIGNAL_CONTROLLER_EVENT, update_sources
        )
        controller.dispatcher.connect(heos_const.SIGNAL_HEOS_EVENT, update_sources)
