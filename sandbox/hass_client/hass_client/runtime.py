"""Remote-capable Home Assistant runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from .api import HomeAssistantAPI
from .config import RemoteConfig
from .remotes.core import context_from_payload, parse_datetime
from .remotes.helpers import RemoteEntityRegistryManager

LOGGER = logging.getLogger(__name__)

from homeassistant.const import (
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
)
from homeassistant.core import (
    Context,
    EventOrigin,
    HomeAssistant as CoreHomeAssistant,
    State,
    callback,
)



class RemoteHomeAssistant(CoreHomeAssistant):
    """Home Assistant subclass with remote websocket sync hooks."""

    def __new__(cls, config_dir: str, **_kwargs: Any) -> RemoteHomeAssistant:
        """Allow extra keyword arguments through __new__."""
        return super().__new__(cls, config_dir)

    def __init__(
        self,
        config_dir: str,
        *,
        remote_config: RemoteConfig | None = None,
    ) -> None:
        """Initialize a remote-capable Home Assistant instance."""
        super().__init__(config_dir)
        self.remote_config = remote_config or RemoteConfig.from_env()
        self.remote_api: HomeAssistantAPI | None = None
        self.remote_ready = False
        self._remote_state_ids: set[str] = set()
        self._remote_unsubscribers: list[Callable[[], None]] = []

        if self.remote_config.enabled:
            self.remote_api = HomeAssistantAPI(
                websocket_url=self.remote_config.websocket_url,
                token=self.remote_config.token,
            )

        self.remote_entity_registry = RemoteEntityRegistryManager(self)

    async def async_setup_remote(self) -> None:
        """Initialize remote sync."""
        if self.remote_ready or self.remote_api is None:
            return

        await self.remote_api.start(ssl=self.remote_config.ssl)
        await self.async_refresh_remote_config()

        if self.remote_config.sync_states:
            await self.async_refresh_remote_states()
            self._remote_unsubscribers.append(
                await self.remote_api.subscribe_events(
                    self._handle_remote_state_changed,
                    EVENT_STATE_CHANGED,
                )
            )
            self._remote_unsubscribers.append(
                await self.remote_api.subscribe_events(
                    self._handle_remote_state_reported,
                    EVENT_STATE_REPORTED,
                )
            )

        if self.remote_config.sync_entity_registry:
            await self.remote_entity_registry.async_setup()

        self.remote_ready = True

    async def async_teardown_remote(self) -> None:
        """Stop remote sync."""
        self.remote_entity_registry.unsubscribe()

        while self._remote_unsubscribers:
            unsubscribe = self._remote_unsubscribers.pop()
            unsubscribe()

        if self.remote_api is not None:
            await self.remote_api.stop()

        self.remote_ready = False

    async def async_refresh_remote_config(self) -> None:
        """Fetch and apply the remote core config."""
        if self.remote_api is None:
            return
        config = await self.remote_api.async_get_config()
        await self.config.async_set_time_zone(config["time_zone"])

    async def async_refresh_remote_states(self) -> None:
        """Fetch the remote state snapshot."""
        if self.remote_api is None:
            return
        states = await self.remote_api.async_get_states()
        self._apply_remote_state_snapshot(states)

    async def async_refresh_remote_entity_registry(self) -> None:
        """Fetch the remote entity registry snapshot."""
        await self.remote_entity_registry.async_refresh()

    @callback
    def _apply_remote_state_snapshot(self, states: list[dict[str, Any]]) -> None:
        """Apply a remote state snapshot without firing change events."""
        remote_ids: set[str] = set()
        state_store = self.states._states

        for state_payload in states:
            state = State.from_dict(state_payload)
            if state is None:
                continue
            entity_id = state.entity_id.lower()
            state_store[entity_id] = state
            remote_ids.add(entity_id)

        for entity_id in self._remote_state_ids - remote_ids:
            if entity_id in state_store:
                del state_store[entity_id]

        self._remote_state_ids = remote_ids

    @callback
    def _handle_remote_state_changed(self, message: dict[str, Any]) -> None:
        """Apply a remote state_changed event locally."""
        event = message["event"]
        data = event["data"]
        entity_id = data["entity_id"].lower()
        context = context_from_payload(event.get("context"))
        timestamp = parse_datetime(event.get("time_fired")).timestamp()

        old_state = self.states.get(entity_id)
        if old_state is not None:
            old_state.expire()

        new_state_payload = data.get("new_state")
        if new_state_payload is None:
            self.states._states.pop(entity_id, None)
            self._remote_state_ids.discard(entity_id)
            self.bus.async_fire_internal(
                EVENT_STATE_CHANGED,
                {
                    "entity_id": entity_id,
                    "old_state": old_state,
                    "new_state": None,
                },
                origin=EventOrigin.remote,
                context=context,
                time_fired=timestamp,
            )
            return

        new_state = State.from_dict(new_state_payload)
        if new_state is None:
            return

        self.states._states[entity_id] = new_state
        self._remote_state_ids.add(entity_id)
        self.bus.async_fire_internal(
            EVENT_STATE_CHANGED,
            {
                "entity_id": entity_id,
                "old_state": old_state,
                "new_state": new_state,
            },
            origin=EventOrigin.remote,
            context=context,
            time_fired=timestamp,
        )

    @callback
    def _handle_remote_state_reported(self, message: dict[str, Any]) -> None:
        """Apply a remote state_reported event locally."""
        event = message["event"]
        data = event["data"]
        entity_id = data["entity_id"].lower()
        context = context_from_payload(event.get("context"))
        state = self.states.get(entity_id)
        new_state_payload = data.get("new_state")
        if state is None or new_state_payload is None:
            return

        last_reported = parse_datetime(data.get("last_reported"))
        old_last_reported = parse_datetime(data.get("old_last_reported"))
        state.last_reported = last_reported
        state._cache["last_reported_timestamp"] = last_reported.timestamp()
        self.bus.async_fire_internal(
            EVENT_STATE_REPORTED,
            {
                "entity_id": entity_id,
                "last_reported": last_reported,
                "old_last_reported": old_last_reported,
                "new_state": state,
            },
            origin=EventOrigin.remote,
            context=context,
            time_fired=parse_datetime(event.get("time_fired")).timestamp(),
        )
