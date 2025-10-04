"""Room management for the Matrix component."""

from __future__ import annotations

import asyncio
import logging

from nio import AsyncClient
from nio.responses import JoinError, JoinResponse, RoomResolveAliasResponse

from homeassistant.core import HomeAssistant

from .types import RoomAlias, RoomAnyID, RoomID

_LOGGER = logging.getLogger(__name__)


class MatrixRooms:
    """Handle Matrix room operations."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncClient,
        listening_rooms: dict[RoomAnyID, RoomID],
    ) -> None:
        """Initialize room manager."""
        self.hass = hass
        self._client = client
        self._listening_rooms = listening_rooms

    async def resolve_room_alias(
        self, room_alias_or_id: RoomAnyID
    ) -> dict[RoomAnyID, RoomID]:
        """Resolve a single RoomAlias if needed."""
        if room_alias_or_id.startswith("!"):
            room_id = RoomID(room_alias_or_id)
            _LOGGER.debug("Will listen to room_id '%s'", room_id)
        elif room_alias_or_id.startswith("#"):
            room_alias = RoomAlias(room_alias_or_id)
            resolve_response = await self._client.room_resolve_alias(room_alias)
            if isinstance(resolve_response, RoomResolveAliasResponse):
                room_id = RoomID(resolve_response.room_id)
                _LOGGER.debug(
                    "Will listen to room_alias '%s' as room_id '%s'",
                    room_alias_or_id,
                    room_id,
                )
            else:
                _LOGGER.error(
                    "Could not resolve '%s' to a room_id: '%s'",
                    room_alias_or_id,
                    resolve_response,
                )
                return {}
        # The config schema guarantees it's a valid room alias or id, so room_id is always set.
        return {room_alias_or_id: room_id}

    async def resolve_room_aliases(self, listening_rooms: list[RoomAnyID]) -> None:
        """Resolve any RoomAliases into RoomIDs for the purpose of client interactions."""
        resolved_rooms = [
            self.hass.async_create_task(
                self.resolve_room_alias(room_alias_or_id), eager_start=False
            )
            for room_alias_or_id in listening_rooms
        ]
        for resolved_room in asyncio.as_completed(resolved_rooms):
            self._listening_rooms |= await resolved_room

    async def join_room(self, room_id: RoomID, room_alias_or_id: RoomAnyID) -> None:
        """Join a room or do nothing if already joined."""
        join_response = await self._client.join(room_id)

        if isinstance(join_response, JoinResponse):
            _LOGGER.debug("Joined or already in room '%s'", room_alias_or_id)
        elif isinstance(join_response, JoinError):
            _LOGGER.error(
                "Could not join room '%s': %s",
                room_alias_or_id,
                join_response,
            )

    async def join_rooms(self) -> None:
        """Join the Matrix rooms that we listen for commands in."""
        rooms = [
            self.hass.async_create_task(
                self.join_room(room_id, room_alias_or_id), eager_start=False
            )
            for room_alias_or_id, room_id in self._listening_rooms.items()
        ]
        await asyncio.wait(rooms)
