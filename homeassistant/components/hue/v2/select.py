"""Select entities for active Hue scene selection per group (room/zone)."""

from __future__ import annotations

from collections import Counter

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.groups import RoomController, ZoneController
from aiohue.v2.models.room import Room
from aiohue.v2.models.scene import Scene as HueScene
from aiohue.v2.models.smart_scene import SmartScene as HueSmartScene
from aiohue.v2.models.zone import Zone

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..bridge import HueBridge, HueConfigEntry
from ..const import DOMAIN
from .entity import HueBaseEntity
from .scene_activity import HueSceneActivityManager

PARALLEL_UPDATES = 0


def _build_scene_option_maps(
    scenes: list[HueScene | HueSmartScene],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build bidirectional option maps for a scene collection."""
    # Sort for a stable option order across restarts and updates.
    scenes = sorted(scenes, key=lambda s: (s.metadata.name, s.id))
    name_counts = Counter(scene.metadata.name for scene in scenes)
    option_to_scene_id: dict[str, str] = {}
    scene_id_to_option: dict[str, str] = {}

    for scene in scenes:
        option = scene.metadata.name
        if name_counts[option] > 1:
            option = f"{option} ({scene.id[:8]})"
        option_to_scene_id[option] = scene.id
        scene_id_to_option[scene.id] = option

    return option_to_scene_id, scene_id_to_option


class SceneActivityBaseEntity(HueBaseEntity):
    """Base class for per-group scene activity entities.

    Attaches to the Hue group (room/zone) device and subscribes to the
    HueSceneActivityManager for active-scene state updates.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _scene_id_to_option: dict[str, str]

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the base scene activity entity for a Hue group."""
        super().__init__(bridge, bridge.api.groups, bridge.api.groups.get(group_id))
        self._manager = manager
        self._group_id = group_id
        self._group_state = manager.get_group_state(group_id)
        # Attach to the virtual Hue group device (same as grouped lights and scenes).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.resource.id)},
            name=self.resource.metadata.name,
        )

    async def async_added_to_hass(self) -> None:
        """Register listener on the manager when added to hass."""
        await super().async_added_to_hass()

        @callback
        def _on_manager_update(_: str) -> None:
            self._group_state = self._manager.get_group_state(self._group_id)
            self.async_write_ha_state()

        self.async_on_remove(
            self._manager.async_add_listener(self._group_id, _on_manager_update)
        )

    def scene_option_matches_name(self, scene_id: str, name: str) -> bool:
        """Return if the current option label still matches an unchanged scene name."""
        option = self._scene_id_to_option.get(scene_id)
        return option in (name, f"{name} ({scene_id[:8]})")


# pylint: disable-next=hass-enforce-class-module
class HueSceneSelectEntity(SceneActivityBaseEntity, SelectEntity):
    """Select entity showing and controlling the active regular scene of a Hue group."""

    _attr_translation_key = "active_scene"

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
        initial_scenes: list[HueScene] | None = None,
    ) -> None:
        """Initialize the regular-scene select entity."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_scene_select"
        self.refresh_options(initial_scenes)

    def refresh_options(self, scenes: list[HueScene] | None = None) -> None:
        """Rebuild the name→id map of regular scenes available for this group."""
        if scenes is None:
            scenes = [
                scene
                for scene in self.bridge.api.scenes.scene
                if scene.group.rid == self._group_id
            ]
        self._option_to_scene_id, self._scene_id_to_option = _build_scene_option_maps(
            scenes
        )

    @property
    def options(self) -> list[str]:
        """Return the available regular scene names for this group."""
        return list(self._option_to_scene_id)

    @property
    def current_option(self) -> str | None:
        """Return the name of the currently active regular scene, if any."""
        if not (active_scene_id := self._group_state.active_scene_id):
            return None
        return self._scene_id_to_option.get(active_scene_id)

    async def async_select_option(self, option: str) -> None:
        """Activate the regular scene with the given name."""
        scene_id = self._option_to_scene_id.get(option)
        if scene_id is None:
            raise HomeAssistantError(
                f"Scene option '{option}' not found in group {self._group_id}"
            )
        await self.bridge.async_request_call(
            self.bridge.api.scenes.scene.recall,
            scene_id,
        )


# pylint: disable-next=hass-enforce-class-module
class HueSmartSceneSelectEntity(SceneActivityBaseEntity, SelectEntity):
    """Select entity showing and controlling the active smart scene of a Hue group."""

    _attr_translation_key = "active_smart_scene"

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
        initial_scenes: list[HueSmartScene] | None = None,
    ) -> None:
        """Initialize the smart-scene select entity."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_smart_scene_select"
        self.refresh_options(initial_scenes)

    def refresh_options(self, scenes: list[HueSmartScene] | None = None) -> None:
        """Rebuild the name→id map of smart scenes available for this group."""
        if scenes is None:
            scenes = [
                scene
                for scene in self.bridge.api.scenes.smart_scene
                if scene.group.rid == self._group_id
            ]
        self._option_to_scene_id, self._scene_id_to_option = _build_scene_option_maps(
            scenes
        )

    @property
    def options(self) -> list[str]:
        """Return the available smart scene names for this group."""
        return list(self._option_to_scene_id)

    @property
    def current_option(self) -> str | None:
        """Return the name of the currently active smart scene, if any."""
        if not (active_smart_scene_id := self._group_state.active_smart_scene_id):
            return None
        return self._scene_id_to_option.get(active_smart_scene_id)

    async def async_select_option(self, option: str) -> None:
        """Activate the smart scene with the given name."""
        scene_id = self._option_to_scene_id.get(option)
        if scene_id is None:
            raise HomeAssistantError(
                f"Smart scene option '{option}' not found in group {self._group_id}"
            )
        await self.bridge.async_request_call(
            self.bridge.api.scenes.smart_scene.recall,
            scene_id,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue scene select entities from a config entry."""
    bridge = config_entry.runtime_data
    api: HueBridgeV2 = bridge.api
    manager = bridge.scene_activity_manager
    assert manager is not None

    # Pre-index scenes by group to avoid an O(groups × scenes) scan per entity
    # when building initial options at startup.
    scenes_by_group: dict[str, list[HueScene]] = {}
    for scene in api.scenes.scene:
        scenes_by_group.setdefault(scene.group.rid, []).append(scene)

    smart_scenes_by_group: dict[str, list[HueSmartScene]] = {}
    for smart_scene in api.scenes.smart_scene:
        smart_scenes_by_group.setdefault(smart_scene.group.rid, []).append(smart_scene)

    scene_entities: dict[str, HueSceneSelectEntity] = {}
    smart_scene_entities: dict[str, HueSmartSceneSelectEntity] = {}

    @callback
    def _on_scene_event(event_type: EventType, scene: HueScene) -> None:
        if entity := scene_entities.get(scene.group.rid):
            # Skip rebuild on status updates where the name hasn't changed.
            if (
                event_type == EventType.RESOURCE_UPDATED
                and entity.scene_option_matches_name(scene.id, scene.metadata.name)
            ):
                return
            entity.refresh_options()
            entity.async_write_ha_state()

    @callback
    def _on_smart_scene_event(event_type: EventType, scene: HueSmartScene) -> None:
        if entity := smart_scene_entities.get(scene.group.rid):
            if (
                event_type == EventType.RESOURCE_UPDATED
                and entity.scene_option_matches_name(scene.id, scene.metadata.name)
            ):
                return
            entity.refresh_options()
            entity.async_write_ha_state()

    scene_event_filter = (
        EventType.RESOURCE_ADDED,
        EventType.RESOURCE_UPDATED,
        EventType.RESOURCE_DELETED,
    )
    config_entry.async_on_unload(
        api.scenes.scene.subscribe(_on_scene_event, event_filter=scene_event_filter)
    )
    config_entry.async_on_unload(
        api.scenes.smart_scene.subscribe(
            _on_smart_scene_event, event_filter=scene_event_filter
        )
    )

    @callback
    def _add_group_entities(group_controller: RoomController | ZoneController) -> None:
        """Create select entities for all groups in the given controller."""
        entities: list[SceneActivityBaseEntity] = []
        for group in group_controller:
            scene_entity = HueSceneSelectEntity(
                bridge, manager, group.id, scenes_by_group.get(group.id)
            )
            smart_scene_entity = HueSmartSceneSelectEntity(
                bridge, manager, group.id, smart_scenes_by_group.get(group.id)
            )
            scene_entities[group.id] = scene_entity
            smart_scene_entities[group.id] = smart_scene_entity
            entities.extend([scene_entity, smart_scene_entity])
        if entities:
            async_add_entities(entities)

        @callback
        def _on_group_added(event_type: EventType, group: Room | Zone) -> None:
            scene_entity = HueSceneSelectEntity(bridge, manager, group.id)
            smart_scene_entity = HueSmartSceneSelectEntity(bridge, manager, group.id)
            scene_entities[group.id] = scene_entity
            smart_scene_entities[group.id] = smart_scene_entity
            async_add_entities([scene_entity, smart_scene_entity])

        config_entry.async_on_unload(
            group_controller.subscribe(
                _on_group_added, event_filter=EventType.RESOURCE_ADDED
            )
        )

    _add_group_entities(api.groups.room)
    _add_group_entities(api.groups.zone)
