"""Select entities for Hue scene selection per group."""

from typing import override

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.room import Room
from aiohue.v2.models.scene import Scene as HueScene
from aiohue.v2.models.smart_scene import SmartScene as HueSmartScene
from aiohue.v2.models.zone import Zone
from aiohue.v2.scene_activity import SceneActivityTracker

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..bridge import HueBridge, HueConfigEntry
from ..const import DOMAIN
from .entity import HueBaseEntity


def _build_scene_option_maps(
    scenes: list[HueScene | HueSmartScene],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build bidirectional option maps for a scene collection."""
    # Sort for a stable option order across restarts and updates.
    scenes = sorted(scenes, key=lambda s: (s.metadata.name, s.id))
    option_to_scene_id: dict[str, str] = {}
    scene_id_to_option: dict[str, str] = {}

    for scene in scenes:
        # Hue allows duplicate scene names within a group; number the repeats.
        option = scene.metadata.name
        repeat = 1
        while option in option_to_scene_id:
            repeat += 1
            option = f"{scene.metadata.name} ({repeat})"
        option_to_scene_id[option] = scene.id
        scene_id_to_option[scene.id] = option

    return option_to_scene_id, scene_id_to_option


# pylint: disable-next=home-assistant-enforce-class-module
class HueSceneSelectEntity(HueBaseEntity, SelectEntity):
    """Select entity showing and controlling the active scene of a Hue group."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_scene"
    _scene_id_to_option: dict[str, str]
    _scene_id_to_name: dict[str, str]

    def __init__(
        self,
        bridge: HueBridge,
        tracker: SceneActivityTracker,
        group_id: str,
        initial_scenes: list[HueScene | HueSmartScene] | None = None,
    ) -> None:
        """Initialize the scene select entity."""
        super().__init__(bridge, bridge.api.groups, bridge.api.groups.get(group_id))
        self._tracker = tracker
        self._group_id = group_id
        self._group_state = tracker.get_group_state(group_id)
        # Attach to the virtual Hue group device (same as grouped lights and scenes).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.resource.id)},
        )
        self._attr_unique_id = f"{group_id}_scene_select"
        self.refresh_options(initial_scenes)

    @override
    async def async_added_to_hass(self) -> None:
        """Register listeners when added to Home Assistant."""
        await super().async_added_to_hass()

        @callback
        def _on_tracker_update(_: str) -> None:
            self._group_state = self._tracker.get_group_state(self._group_id)
            self.async_write_ha_state()

        self.async_on_remove(
            self._tracker.subscribe(self._group_id, _on_tracker_update)
        )
        self.async_on_remove(
            self.bridge.api.scenes.subscribe(
                self._handle_scene_event,
                event_filter=(
                    EventType.RESOURCE_ADDED,
                    EventType.RESOURCE_UPDATED,
                    EventType.RESOURCE_DELETED,
                ),
            )
        )

    @callback
    def _handle_scene_event(
        self, event_type: EventType, scene: HueScene | HueSmartScene
    ) -> None:
        """Refresh options when this group's scenes change."""
        if scene.group.rid != self._group_id:
            return
        # Skip rebuild on status updates where the name hasn't changed.
        if event_type == EventType.RESOURCE_UPDATED and self.scene_option_matches_name(
            scene.id, scene.metadata.name
        ):
            return
        self.refresh_options()
        self.async_write_ha_state()

    def scene_option_matches_name(self, scene_id: str, name: str) -> bool:
        """Return if the current option label still matches an unchanged scene name."""
        return self._scene_id_to_name.get(scene_id) == name

    def refresh_options(
        self, scenes: list[HueScene | HueSmartScene] | None = None
    ) -> None:
        """Rebuild the name-to-ID map of scenes available for this group."""
        if scenes is None:
            scenes = [
                scene
                for scene in self.bridge.api.scenes
                if scene.group.rid == self._group_id
            ]
        self._scene_id_to_name = {scene.id: scene.metadata.name for scene in scenes}
        self._option_to_scene_id, self._scene_id_to_option = _build_scene_option_maps(
            scenes
        )

    @property
    @override
    def options(self) -> list[str]:
        """Return the available scene names for this group."""
        return list(self._option_to_scene_id)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the name of the currently active scene."""
        if not (scene_id := self._group_state.scene_id):
            return None
        return self._scene_id_to_option.get(scene_id)

    @override
    async def async_select_option(self, option: str) -> None:
        """Activate the scene with the given name."""
        scene_id = self._option_to_scene_id[option]
        await self.bridge.async_request_call(
            self.bridge.api.scenes.recall,
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
    tracker = bridge.scene_activity_tracker
    assert tracker is not None

    # Pre-index scenes by group to avoid an O(groups x scenes) startup scan.
    scenes_by_group: dict[str, list[HueScene | HueSmartScene]] = {}
    for scene in api.scenes:
        scenes_by_group.setdefault(scene.group.rid, []).append(scene)

    @callback
    def _on_group_added(_: EventType, group: Room | Zone) -> None:
        async_add_entities([HueSceneSelectEntity(bridge, tracker, group.id)])

    for group_controller in (api.groups.room, api.groups.zone):
        async_add_entities(
            HueSceneSelectEntity(
                bridge, tracker, group.id, scenes_by_group.get(group.id)
            )
            for group in group_controller
        )
        config_entry.async_on_unload(
            group_controller.subscribe(
                _on_group_added, event_filter=EventType.RESOURCE_ADDED
            )
        )
