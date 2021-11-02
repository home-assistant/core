"""Support for select platform for Hue scenes (V2 only)."""
from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.scenes import ScenesController
from aiohue.v2.models.scene import Scene as HueScene

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, Scene as SceneEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import HueBridge
from .const import DOMAIN, LOGGER
from .v2.entity import HueBaseEntity

LOGGER = LOGGER.getChild(SCENE_DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue select platform from Hue group scenes."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    if not bridge.use_v2:
        # should not happen, but just in case
        raise NotImplementedError("Scene support is only available for V2 bridges")

    # add entities for all scenes
    @callback
    def async_add_entity(event_type: EventType, resource: HueScene) -> None:
        """Add entity from Hue resource."""
        async_add_entities([HueSceneEntity(config_entry, api.scenes, resource, api)])

    # add all current items in controller
    for item in api.scenes:
        async_add_entity(EventType.RESOURCE_ADDED, item)

    # register listener for new items only
    config_entry.async_on_unload(
        api.scenes.subscribe(async_add_entity, event_filter=EventType.RESOURCE_ADDED)
    )


class HueSceneEntity(HueBaseEntity, SceneEntity):
    """Representation of a Scene entity from HUE Scenes."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        controller: ScenesController,
        resource: HueScene,
        api: HueBridgeV2,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(config_entry, controller, resource)
        self.resource = resource
        self.controller = controller
        self.api = api
        self._active_scene = None

    @property
    def name(self) -> str:
        """Return default entity name."""
        group = self.controller.get_group(self.resource.id)
        return f"{group.metadata.name} - {self.resource.metadata.name}"

    @property
    def is_dynamic(self) -> bool:
        """Return if this scene has a dynamic color palette."""
        if self.resource.palette.color and len(self.resource.palette.color) > 1:
            return True
        if (
            self.resource.palette.color_temperature
            and len(self.resource.palette.color_temperature) > 1
        ):
            return True
        return False

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate Hue scene."""
        transition = kwargs.get("transition")
        if transition is not None:
            # hue transition duration is in steps of 100 ms
            transition = int(transition * 100)
        dynamic = kwargs.get("dynamic", self.is_dynamic)
        await self.controller.recall(
            self.resource.id, dynamic=dynamic, duration=transition
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        group = self.controller.get_group(self.resource.id)
        brightness = None
        if palette := self.resource.palette:
            if palette.dimming:
                brightness = palette.dimming[0].brightness
        if brightness is None:
            # get brightness from actions
            for action in self.resource.actions:
                if action.action.dimming:
                    brightness = action.action.dimming.brightness
                    break
        return {
            "is_hue_scene": True,
            "group_name": group.metadata.name,
            "group_type": group.type.value,
            "name": self.resource.metadata.name,
            "speed": self.resource.speed,
            "brightness": brightness,
            "is_dynamic": self.is_dynamic,
        }
