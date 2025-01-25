"""Denon HEOS Media Player."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pyheos import Heos, HeosError, HeosPlayer, const as heos_const

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType

from . import services
from .const import DOMAIN, SIGNAL_HEOS_PLAYER_ADDED, SIGNAL_HEOS_UPDATED
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

    group_manager = GroupManager(hass, controller, players)

    entry.runtime_data = HeosRuntimeData(coordinator, group_manager, players)

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
