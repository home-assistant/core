"""Shared manager for tracking active Hue scenes per group.

This centralizes listening to raw scene events and keeps lightweight
dataclasses with the current active regular scene / smart scene and
related metadata (mode, last recall, speed, brightness).

Sensor and binary_sensor entities subscribe to the manager for updates
instead of each registering their own low-level event listener.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.scene import Scene as HueScene
from aiohue.v2.models.smart_scene import SmartScene as HueSmartScene, SmartSceneState

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from ..const import DOMAIN

UpdateListener = Callable[[str], None]


@dataclass(slots=True)
class GroupSceneState:
    """Holds active scene related data for a Hue group (room/zone).

    The last recall timestamp is stored as an aware datetime (UTC) when available.
    """

    # Regular scene state
    active_scene_entity_id: str | None = None
    active_scene_name: str | None = None
    active_scene_mode: str | None = None  # static | dynamic_palette
    active_scene_last_recall: datetime | None = None

    # Smart scene state
    active_smart_scene_entity_id: str | None = None
    active_smart_scene_name: str | None = None


class HueSceneActivityManager:
    """Track active (smart) scenes per Hue group and dispatch updates."""

    def __init__(self, hass: HomeAssistant, api: HueBridgeV2) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.api = api
        self.er = er.async_get(hass)
        self._group_states: dict[str, GroupSceneState] = defaultdict(GroupSceneState)
        self._listeners: dict[str, list[UpdateListener]] = defaultdict(list)
        self._unsub: CALLBACK_TYPE | None = None

    def start(self) -> None:
        """Begin listening to raw scene events (idempotent)."""
        if self._unsub is not None:
            return

        @callback
        def _handle_scene_event(
            event_type: EventType, scene: HueScene | HueSmartScene
        ) -> None:
            if not scene.id:
                return
            entity_id = self.er.async_get_entity_id("scene", "hue", scene.id)
            group_id = scene.group.rid
            group_state = self._group_states[group_id]

            updated = False
            if isinstance(scene, HueScene):
                active_mode = getattr(scene, "_ha_active_mode", "inactive")
                if active_mode != "inactive":
                    group_state.active_scene_entity_id = entity_id
                    group_state.active_scene_name = scene.metadata.name
                    group_state.active_scene_mode = active_mode
                    group_state.active_scene_last_recall = getattr(
                        scene, "_ha_last_recall", None
                    )
                    updated = True

                elif group_state.active_scene_entity_id == entity_id:
                    group_state.active_scene_entity_id = None
                    group_state.active_scene_name = None
                    group_state.active_scene_mode = None
                    group_state.active_scene_last_recall = None
                    updated = True
            elif isinstance(scene, HueSmartScene):
                if scene.state == SmartSceneState.ACTIVE:
                    group_state.active_smart_scene_entity_id = entity_id
                    group_state.active_smart_scene_name = scene.metadata.name
                    updated = True
                elif group_state.active_smart_scene_entity_id == entity_id:
                    group_state.active_smart_scene_entity_id = None
                    group_state.active_smart_scene_name = None
                    updated = True

            if updated:
                for listener in list(self._listeners[group_id]):
                    listener(group_id)

        self._unsub = self.api.scenes.subscribe(_handle_scene_event)

    def stop(self) -> None:
        """Stop listening to events."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    def get_group_state(self, group_id: str) -> GroupSceneState:
        """Return (and create) state holder for group."""
        return self._group_states[group_id]

    def async_add_listener(
        self, group_id: str, listener: UpdateListener
    ) -> CALLBACK_TYPE:
        """Add a listener and return remove callback."""
        self._listeners[group_id].append(listener)

        @callback
        def _remove() -> None:
            self._listeners[group_id].remove(listener)
            if not self._listeners[group_id] and not any(self._listeners.values()):
                # No listeners left anywhere -> optional future stop
                return

        return _remove


def get_or_create_scene_activity_manager(
    hass: HomeAssistant, api: HueBridgeV2
) -> HueSceneActivityManager:
    """Return a shared manager instance for this hass instance + bridge."""
    key = f"{DOMAIN}_scene_activity_{id(api)}"
    if (mgr := hass.data.get(key)) is None:
        mgr = HueSceneActivityManager(hass, api)
        mgr.start()
        hass.data[key] = mgr
    return mgr
