"""Support forked_daapd media player."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
from typing import Any

from pyforked_daapd import ForkedDaapdAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
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

    @property
    def api(self) -> ForkedDaapdAPI:
        """Return the API object."""
        return self._api

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
        update_events = {}
        _LOGGER.debug("Updating %s", update_types)
        if (
            "queue" in update_types
        ):  # update queue, queue before player for async_play_media
            if queue := await self._api.get_request("queue"):
                update_events["queue"] = asyncio.Event()
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_QUEUE.format(self._entry_id),
                    queue,
                    update_events["queue"],
                )
        # order of below don't matter
        if not {"outputs", "volume"}.isdisjoint(update_types):  # update outputs
            if outputs := await self._api.get_request("outputs"):
                outputs = outputs["outputs"]
                update_events["outputs"] = (
                    asyncio.Event()
                )  # only for master, zones should ignore
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_OUTPUTS.format(self._entry_id),
                    outputs,
                    update_events["outputs"],
                )
                self._add_zones(outputs)
        if not {"database"}.isdisjoint(update_types):
            pipes, playlists = await asyncio.gather(
                self._api.get_pipes(), self._api.get_playlists()
            )
            update_events["database"] = asyncio.Event()
            async_dispatcher_send(
                self.hass,
                SIGNAL_UPDATE_DATABASE.format(self._entry_id),
                pipes,
                playlists,
                update_events["database"],
            )
        if not {"update", "config"}.isdisjoint(update_types):  # not supported
            _LOGGER.debug("update/config notifications neither requested nor supported")
        if not {"player", "options", "volume"}.isdisjoint(
            update_types
        ):  # update player
            if player := await self._api.get_request("player"):
                update_events["player"] = asyncio.Event()
                if update_events.get("queue"):
                    await update_events[
                        "queue"
                    ].wait()  # make sure queue done before player for async_play_media
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_PLAYER.format(self._entry_id),
                    player,
                    update_events["player"],
                )
        if update_events:
            await asyncio.wait(
                [asyncio.create_task(event.wait()) for event in update_events.values()]
            )  # make sure callbacks done before update
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
