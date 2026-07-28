"""Track active Hue scenes per group."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.scene import Scene, SceneActiveStatus
from aiohue.v2.models.smart_scene import SmartScene, SmartSceneState

if TYPE_CHECKING:
    from aiohue.v2.controllers.scenes import ScenesController

UpdateListener = Callable[[str], None]


@dataclass(slots=True)
class GroupSceneState:
    """Hold active scene data for a Hue group.

    A smart scene and its effective regular scene can be active at the same time.
    In that case, both ``smart_scene_id`` and ``scene_id`` are set.
    """

    # Regular scene state
    scene_id: str | None = None
    scene_mode: SceneActiveStatus | None = None
    scene_last_recall: datetime | None = None
    scene_speed: float | None = None
    scene_brightness: float | None = None

    # Smart scene state
    smart_scene_id: str | None = None


class SceneActivityTracker:
    """Track active scenes per Hue group and dispatch updates."""

    def __init__(self, scenes: ScenesController) -> None:
        """Initialize the tracker."""
        self._scenes = scenes
        self._group_states: dict[str, GroupSceneState] = defaultdict(GroupSceneState)
        self._listeners: dict[str, list[UpdateListener]] = defaultdict(list)
        self._unsub: Callable[[], None] | None = None

    def start(self) -> None:
        """Subscribe to scene events and seed initial state."""
        if self._unsub is not None:
            return

        def _handle_scene_event(
            event_type: EventType, scene: Scene | SmartScene
        ) -> None:
            if event_type == EventType.RESOURCE_DELETED:
                self._clear_deleted_scene(scene)
                return
            if self._apply_scene_update(scene):
                group_id = scene.group.rid
                for listener in list(self._listeners[group_id]):
                    listener(group_id)

        self._unsub = self._scenes.subscribe(_handle_scene_event)

        updated_group_ids: set[str] = set()
        for smart_scene in self._scenes.smart_scene:
            if self._apply_scene_update(smart_scene):
                updated_group_ids.add(smart_scene.group.rid)
        for scene in self._scenes.scene:
            if self._apply_scene_update(scene):
                updated_group_ids.add(scene.group.rid)
        for group_id in updated_group_ids:
            for listener in list(self._listeners.get(group_id, [])):
                listener(group_id)

    def stop(self) -> None:
        """Stop listening to scene events."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    def get_group_state(self, group_id: str) -> GroupSceneState:
        """Return the state holder for a group."""
        return self._group_states[group_id]

    def subscribe(self, group_id: str, listener: UpdateListener) -> Callable[[], None]:
        """Register a listener for a group."""
        self._listeners[group_id].append(listener)

        def _remove() -> None:
            self._listeners[group_id].remove(listener)

        return _remove

    def _clear_deleted_scene(self, scene: Scene | SmartScene) -> None:
        """Clear group state when a tracked scene is deleted."""
        if not isinstance(scene, (Scene, SmartScene)):
            return
        group_id = scene.group.rid
        group_state = self._group_states.get(group_id)
        if group_state is None:
            return
        changed = False
        if isinstance(scene, Scene) and group_state.scene_id == scene.id:
            group_state.scene_id = None
            group_state.scene_mode = None
            group_state.scene_last_recall = None
            group_state.scene_speed = None
            group_state.scene_brightness = None
            changed = True
        elif isinstance(scene, SmartScene) and group_state.smart_scene_id == scene.id:
            group_state.smart_scene_id = None
            changed = True
        if changed:
            for listener in list(self._listeners.get(group_id, [])):
                listener(group_id)

    def _apply_scene_update(self, scene: Scene | SmartScene) -> bool:
        """Apply scene state to group tracking."""
        if not scene.id:
            return False
        group_state = self._group_states[scene.group.rid]
        if isinstance(scene, Scene):
            return self._apply_regular_scene_update(scene, group_state)
        if isinstance(scene, SmartScene):
            return self._apply_smart_scene_update(scene, group_state)
        return False

    def _apply_regular_scene_update(
        self, scene: Scene, group_state: GroupSceneState
    ) -> bool:
        """Update group state from a regular scene event."""
        if scene.status is None:
            return False
        if scene.status.active != SceneActiveStatus.INACTIVE:
            group_state.scene_id = scene.id
            group_state.scene_mode = scene.status.active
            group_state.scene_last_recall = scene.status.last_recall
            group_state.scene_speed = scene.speed
            group_state.scene_brightness = next(
                (
                    action.action.dimming.brightness
                    for action in scene.actions
                    if action.action.dimming is not None
                ),
                None,
            )
            return True
        if group_state.scene_id == scene.id:
            group_state.scene_id = None
            group_state.scene_mode = None
            group_state.scene_last_recall = None
            group_state.scene_speed = None
            group_state.scene_brightness = None
            return True
        return False

    def _apply_smart_scene_update(
        self, scene: SmartScene, group_state: GroupSceneState
    ) -> bool:
        """Update group state from a smart scene event."""
        if scene.state == SmartSceneState.ACTIVE:
            group_state.smart_scene_id = scene.id
            return True
        if group_state.smart_scene_id == scene.id:
            group_state.smart_scene_id = None
            return True
        return False
