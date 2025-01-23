"""Denon HEOS Media Player."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pyheos import Heos, HeosError, HeosPlayer, const as heos_const

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import services
from .const import (
    COMMAND_RETRY_ATTEMPTS,
    COMMAND_RETRY_DELAY,
    DOMAIN,
    SIGNAL_HEOS_PLAYER_ADDED,
    SIGNAL_HEOS_UPDATED,
)
from .coordinator import HeosCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

MIN_UPDATE_SOURCES = timedelta(seconds=1)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


@dataclass
class HeosRuntimeData:
    """Runtime data and coordinators for HEOS config entries."""

    coordinator: HeosCoordinator
    group_manager: GroupManager
    source_manager: SourceManager
    players: dict[int, HeosPlayer]


type HeosConfigEntry = ConfigEntry[HeosRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HEOS component."""
    services.register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Initialize config entry which represents the HEOS controller."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    # Migrate non-string device identifiers.
    device_registry = dr.async_get(hass)
    for device in device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    ):
        for domain, player_id in device.identifiers:
            if domain == DOMAIN and not isinstance(player_id, str):
                device_registry.async_update_device(
                    device.id, new_identifiers={(DOMAIN, str(player_id))}
                )
            break

    coordinator = HeosCoordinator(hass, entry)
    await coordinator.async_setup()
    # Preserve existing logic until migrated into coordinator
    controller = coordinator.heos
    players = controller.players
    favorites = coordinator.favorites
    inputs = coordinator.inputs

    source_manager = SourceManager(favorites, inputs)
    source_manager.connect_update(hass, controller)

    group_manager = GroupManager(hass, controller, players)

    entry.runtime_data = HeosRuntimeData(
        coordinator, group_manager, source_manager, players
    )

    group_manager.connect_update()
    entry.async_on_unload(group_manager.disconnect_update)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeosConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class GroupManager:
    """Class that manages HEOS groups."""

    def __init__(
        self, hass: HomeAssistant, controller: Heos, players: dict[int, HeosPlayer]
    ) -> None:
        """Init group manager."""
        self._hass = hass
        self._group_membership: dict[str, list[str]] = {}
        self._disconnect_player_added = None
        self._initialized = False
        self.controller = controller
        self.players = players
        self.entity_id_map: dict[int, str] = {}

    def _get_entity_id_to_player_id_map(self) -> dict:
        """Return mapping of all HeosMediaPlayer entity_ids to player_ids."""
        return {v: k for k, v in self.entity_id_map.items()}

    async def async_get_group_membership(self) -> dict[str, list[str]]:
        """Return all group members for each player as entity_ids."""
        group_info_by_entity_id: dict[str, list[str]] = {
            player_entity_id: []
            for player_entity_id in self._get_entity_id_to_player_id_map()
        }

        try:
            groups = await self.controller.get_groups()
        except HeosError as err:
            _LOGGER.error("Unable to get HEOS group info: %s", err)
            return group_info_by_entity_id

        player_id_to_entity_id_map = self.entity_id_map
        for group in groups.values():
            leader_entity_id = player_id_to_entity_id_map.get(group.lead_player_id)
            member_entity_ids = [
                player_id_to_entity_id_map[member]
                for member in group.member_player_ids
                if member in player_id_to_entity_id_map
            ]
            # Make sure the group leader is always the first element
            group_info = [leader_entity_id, *member_entity_ids]
            if leader_entity_id:
                group_info_by_entity_id[leader_entity_id] = group_info  # type: ignore[assignment]
                for member_entity_id in member_entity_ids:
                    group_info_by_entity_id[member_entity_id] = group_info  # type: ignore[assignment]

        return group_info_by_entity_id

    async def async_join_players(
        self, leader_id: int, member_entity_ids: list[str]
    ) -> None:
        """Create a group a group leader and member players."""
        # Resolve HEOS player_id for each member entity_id
        entity_id_to_player_id_map = self._get_entity_id_to_player_id_map()
        member_ids: list[int] = []
        for member in member_entity_ids:
            member_id = entity_id_to_player_id_map.get(member)
            if not member_id:
                raise HomeAssistantError(
                    f"The group member {member} could not be resolved to a HEOS player."
                )
            member_ids.append(member_id)

        await self.controller.create_group(leader_id, member_ids)

    async def async_unjoin_player(self, player_id: int):
        """Remove `player_entity_id` from any group."""
        await self.controller.create_group(player_id, [])

    async def async_update_groups(self) -> None:
        """Update the group membership from the controller."""
        if groups := await self.async_get_group_membership():
            self._group_membership = groups
            _LOGGER.debug("Groups updated due to change event")
            # Let players know to update
            async_dispatcher_send(self._hass, SIGNAL_HEOS_UPDATED)
        else:
            _LOGGER.debug("Groups empty")

    @callback
    def connect_update(self):
        """Connect listener for when groups change and signal player update."""

        async def _on_controller_event(event: str, data: Any | None) -> None:
            if event == heos_const.EVENT_GROUPS_CHANGED:
                await self.async_update_groups()

        self.controller.add_on_controller_event(_on_controller_event)
        self.controller.add_on_connected(self.async_update_groups)

        # When adding a new HEOS player we need to update the groups.
        async def _async_handle_player_added():
            # Avoid calling async_update_groups when the entity_id map has not been
            # fully populated yet. This may only happen during early startup.
            if len(self.players) <= len(self.entity_id_map) and not self._initialized:
                self._initialized = True
                await self.async_update_groups()

        self._disconnect_player_added = async_dispatcher_connect(
            self._hass, SIGNAL_HEOS_PLAYER_ADDED, _async_handle_player_added
        )

    @callback
    def disconnect_update(self):
        """Disconnect the listeners."""
        if self._disconnect_player_added:
            self._disconnect_player_added()
            self._disconnect_player_added = None

    @callback
    def register_media_player(self, player_id: int, entity_id: str) -> CALLBACK_TYPE:
        """Register a media player player_id with it's entity_id so it can be resolved later."""
        self.entity_id_map[player_id] = entity_id
        return lambda: self.unregister_media_player(player_id)

    @callback
    def unregister_media_player(self, player_id) -> None:
        """Remove a media player player_id from the entity_id map."""
        self.entity_id_map.pop(player_id, None)

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
            await player.play_preset_station(index)
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
            await player.play_input_source(input_source.media_id)
            return

        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_source",
            translation_placeholders={"source": source},
        )

    def get_current_source(self, now_playing_media):
        """Determine current source from now playing media."""
        # Match input by input_name:media_id
        if now_playing_media.source_id == heos_const.MUSIC_SOURCE_AUX_INPUT:
            return next(
                (
                    input_source.name
                    for input_source in self.inputs
                    if input_source.media_id == now_playing_media.media_id
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

    @callback
    def connect_update(self, hass: HomeAssistant, controller: Heos) -> None:
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
                except HeosError as error:
                    if retry_attempts < self.max_retry_attempts:
                        retry_attempts += 1
                        _LOGGER.debug(
                            "Error retrieving sources and will retry: %s", error
                        )
                        await asyncio.sleep(self.retry_delay)
                    else:
                        _LOGGER.error("Unable to update sources: %s", error)
                        return None
                else:
                    return favorites, inputs

        async def _update_sources() -> None:
            # If throttled, it will return None
            if sources := await get_sources():
                self.favorites, self.inputs = sources
                self.source_list = self._build_source_list()
                _LOGGER.debug("Sources updated due to changed event")
                # Let players know to update
                async_dispatcher_send(hass, SIGNAL_HEOS_UPDATED)

        async def _on_controller_event(event: str, data: Any | None) -> None:
            if event in (
                heos_const.EVENT_SOURCES_CHANGED,
                heos_const.EVENT_USER_CHANGED,
            ):
                await _update_sources()

        controller.add_on_connected(_update_sources)
        controller.add_on_user_credentials_invalid(_update_sources)
        controller.add_on_controller_event(_on_controller_event)
