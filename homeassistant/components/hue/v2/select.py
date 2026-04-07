"""Select entities for active Hue scene selection per group (room/zone)."""

from __future__ import annotations

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.scene import Scene as HueScene
from aiohue.v2.models.smart_scene import SmartScene as HueSmartScene

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..bridge import HueBridge, HueConfigEntry
from ..const import DOMAIN
from .entity import HueBaseEntity
from .scene_activity import HueSceneActivityManager

PARALLEL_UPDATES = 0


class SceneActivityBaseEntity(HueBaseEntity):
    """Base class for per-group scene activity entities.

    Attaches to the Hue group (room/zone) device and subscribes to the
    HueSceneActivityManager for active-scene state updates.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

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


# pylint: disable-next=hass-enforce-class-module
class HueSceneSelectEntity(SceneActivityBaseEntity, SelectEntity):
    """Select entity showing and controlling the active regular scene of a Hue group."""

    _attr_translation_key = "active_scene"

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the regular-scene select entity."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_scene_select"
        self._refresh_options()

    def _refresh_options(self) -> None:
        """Rebuild the list of regular scene names available for this group."""
        self._scene_names = [
            scene.metadata.name
            for scene in self.bridge.api.scenes.scene
            if scene.group.rid == self._group_id
        ]

    @property
    def options(self) -> list[str]:
        """Return the available regular scene names for this group."""
        return self._scene_names

    @property
    def current_option(self) -> str | None:
        """Return the name of the currently active regular scene, if any."""
        return self._group_state.active_scene_name

    async def async_select_option(self, option: str) -> None:
        """Activate the regular scene with the given name."""
        scene = next(
            (
                s
                for s in self.bridge.api.scenes.scene
                if s.metadata.name == option and s.group.rid == self._group_id
            ),
            None,
        )
        if scene is None:
            return
        await self.bridge.async_request_call(
            self.bridge.api.scenes.scene.recall,
            scene.id,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to scene resource events to keep options list current."""
        await super().async_added_to_hass()

        @callback
        def _on_scene_event(
            event_type: EventType, scene: HueScene | HueSmartScene
        ) -> None:
            if not isinstance(scene, HueScene):
                return
            if scene.group.rid != self._group_id:
                return
            self._refresh_options()
            self.async_write_ha_state()

        self.async_on_remove(self.bridge.api.scenes.subscribe(_on_scene_event))


# pylint: disable-next=hass-enforce-class-module
class HueSmartSceneSelectEntity(SceneActivityBaseEntity, SelectEntity):
    """Select entity showing and controlling the active smart scene of a Hue group."""

    _attr_translation_key = "active_smart_scene"

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the smart-scene select entity."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_smart_scene_select"
        self._refresh_options()

    def _refresh_options(self) -> None:
        """Rebuild the list of smart scene names available for this group."""
        self._scene_names = [
            scene.metadata.name
            for scene in self.bridge.api.scenes.smart_scene
            if scene.group.rid == self._group_id
        ]

    @property
    def options(self) -> list[str]:
        """Return the available smart scene names for this group."""
        return self._scene_names

    @property
    def current_option(self) -> str | None:
        """Return the name of the currently active smart scene, if any."""
        return self._group_state.active_smart_scene_name

    async def async_select_option(self, option: str) -> None:
        """Activate the smart scene with the given name."""
        scene = next(
            (
                s
                for s in self.bridge.api.scenes.smart_scene
                if s.metadata.name == option and s.group.rid == self._group_id
            ),
            None,
        )
        if scene is None:
            return
        await self.bridge.async_request_call(
            self.bridge.api.scenes.smart_scene.recall,
            scene.id,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to smart scene resource events to keep options list current."""
        await super().async_added_to_hass()

        @callback
        def _on_scene_event(
            event_type: EventType, scene: HueScene | HueSmartScene
        ) -> None:
            if not isinstance(scene, HueSmartScene):
                return
            if scene.group.rid != self._group_id:
                return
            self._refresh_options()
            self.async_write_ha_state()

        self.async_on_remove(self.bridge.api.scenes.subscribe(_on_scene_event))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue scene select entities from a config entry."""
    bridge = config_entry.runtime_data
    api: HueBridgeV2 = bridge.api
    assert (manager := bridge.scene_activity_manager) is not None

    @callback
    def _add_group_entities(group_controller) -> None:
        """Create select entities for all groups in the given controller."""
        entities: list[SceneActivityBaseEntity] = []
        for group in group_controller:
            entities.append(HueSceneSelectEntity(bridge, manager, group.id))
            entities.append(HueSmartSceneSelectEntity(bridge, manager, group.id))
        if entities:
            async_add_entities(entities)

        @callback
        def _on_group_added(event_type: EventType, group) -> None:
            async_add_entities(
                [
                    HueSceneSelectEntity(bridge, manager, group.id),
                    HueSmartSceneSelectEntity(bridge, manager, group.id),
                ]
            )

        config_entry.async_on_unload(
            group_controller.subscribe(
                _on_group_added, event_filter=EventType.RESOURCE_ADDED
            )
        )

    _add_group_entities(api.groups.room)
    _add_group_entities(api.groups.zone)
