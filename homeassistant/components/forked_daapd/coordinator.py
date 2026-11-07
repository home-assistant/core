"""Support forked_daapd media player."""

import asyncio
from collections.abc import Sequence
import logging
from typing import Any

from pyforked_daapd import ForkedDaapdAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    SIGNAL_ADD_ZONES,
    SIGNAL_UPDATE_DATABASE,
    SIGNAL_UPDATE_MASTER,
    SIGNAL_UPDATE_OUTPUTS,
    SIGNAL_UPDATE_PLAYER,
    SIGNAL_UPDATE_QUEUE,
)

type ForkedDaapdConfigEntry = ConfigEntry[ForkedDaapdUpdater]

_LOGGER = logging.getLogger(__name__)

WS_NOTIFY_EVENT_TYPES = ["player", "outputs", "volume", "options", "queue", "database"]
WEBSOCKET_RECONNECT_TIME = 30  # seconds


class ForkedDaapdUpdater:
    """Manage updates for the forked-daapd device."""

    def __init__(self, hass: HomeAssistant, api: ForkedDaapdAPI, entry_id: str) -> None:
        """Initialize."""
        self.hass = hass
        self._api = api
        self.websocket_handler: asyncio.Task[None] | None = None
        self._all_output_ids: set[str] = set()
        self._entry_id = entry_id
        self.outputs: list[dict[str, Any]] = []

    @property
    def api(self) -> ForkedDaapdAPI:
        """Return the API object."""
        return self._api

    @property
    def group_members(self) -> list[str]:
        """Return the enabled server and selected output entities."""
        entity_registry = er.async_get(self.hass)
        entries = {
            entry.unique_id: entry.entity_id
            for entry in er.async_entries_for_config_entry(
                entity_registry, self._entry_id
            )
            if entry.domain == Platform.MEDIA_PLAYER
            and entry.platform == DOMAIN
            and not entry.disabled
        }
        members = [
            entity_id
            for output in self.outputs
            if output["selected"]
            and (entity_id := entries.get(f"{self._entry_id}-{output['id']}"))
            is not None
        ]
        if master_entity_id := entries.get(self._entry_id):
            members.insert(0, master_entity_id)
        return members

    async def async_join_players(self, group_members: list[str]) -> None:
        """Validate and enable outputs for the current playback."""
        entity_registry = er.async_get(self.hass)
        known_output_ids = {output["id"] for output in self.outputs}
        output_ids: list[str] = []
        for entity_id in group_members:
            if not (entity_entry := entity_registry.async_get(entity_id)):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entity_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )
            if (
                entity_entry.platform != DOMAIN
                or entity_entry.config_entry_id != self._entry_id
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="not_forked_daapd_output",
                    translation_placeholders={"entity_id": entity_id},
                )
            if entity_entry.unique_id == self._entry_id:
                continue
            output_id = entity_entry.unique_id.removeprefix(f"{self._entry_id}-")
            # Registry entries persist after an output disappears from the server.
            if output_id not in known_output_ids:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="output_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )
            output_ids.append(output_id)

        await asyncio.gather(
            *(
                self._api.change_output(output_id, selected=True)
                for output_id in output_ids
            )
        )

    async def async_init(self) -> None:
        """Perform async portion of class initialization."""
        if not (server_config := await self._api.get_request("config")):
            raise PlatformNotReady
        if websocket_port := server_config.get("websocket_port"):
            self.websocket_handler = asyncio.create_task(
                self._api.start_websocket_handler(
                    websocket_port,
                    WS_NOTIFY_EVENT_TYPES,
                    self._update,
                    WEBSOCKET_RECONNECT_TIME,
                    self._disconnected_callback,
                )
            )
        else:
            _LOGGER.error("Invalid websocket port")

    async def _disconnected_callback(self) -> None:
        """Send update signals when the websocket gets disconnected."""
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATE_MASTER.format(self._entry_id), False
        )
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATE_OUTPUTS.format(self._entry_id), []
        )

    async def _update(self, update_types_sequence: Sequence[str]) -> None:
        """Private update method."""
        update_types = set(update_types_sequence)
        updated = False
        _LOGGER.debug("Updating %s", update_types)
        if (
            "queue" in update_types
        ):  # update queue, queue before player for async_play_media
            if queue := await self._api.get_request("queue"):
                updated = True
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_QUEUE.format(self._entry_id),
                    queue,
                )
        # order of below don't matter
        if not {"outputs", "volume"}.isdisjoint(update_types):  # update outputs
            if outputs := await self._api.get_request("outputs"):
                outputs = outputs["outputs"]
                self.outputs = outputs
                updated = True
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_OUTPUTS.format(self._entry_id),
                    outputs,
                )
                self._add_zones(outputs)
        if not {"database"}.isdisjoint(update_types):
            pipes, playlists = await asyncio.gather(
                self._api.get_pipes(), self._api.get_playlists()
            )
            updated = True
            async_dispatcher_send(
                self.hass,
                SIGNAL_UPDATE_DATABASE.format(self._entry_id),
                pipes,
                playlists,
            )
        if not {"update", "config"}.isdisjoint(update_types):  # not supported
            _LOGGER.debug("update/config notifications neither requested nor supported")
        if not {"player", "options", "volume"}.isdisjoint(
            update_types
        ):  # update player
            if player := await self._api.get_request("player"):
                updated = True
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_PLAYER.format(self._entry_id),
                    player,
                )
        if updated:
            async_dispatcher_send(
                self.hass, SIGNAL_UPDATE_MASTER.format(self._entry_id), True
            )

    def _add_zones(self, outputs: list[dict[str, Any]]) -> None:
        outputs_to_add: list[dict[str, Any]] = []
        for output in outputs:
            if output["id"] not in self._all_output_ids:
                self._all_output_ids.add(output["id"])
                outputs_to_add.append(output)
        if outputs_to_add:
            async_dispatcher_send(
                self.hass,
                SIGNAL_ADD_ZONES.format(self._entry_id),
                self._api,
                outputs_to_add,
            )
