"""Support for scene platform for Hue scenes (V2 only)."""
from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.scenes import ScenesController
from aiohue.v2.models.scene import Scene as HueScene

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import HueBridge
from .const import DOMAIN
from .v2.entity import HueBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene platform from Hue group scenes."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    if bridge.api_version == 1:
        # should not happen, but just in case
        raise NotImplementedError("Scene support is only available for V2 bridges")

    # add entities for all scenes
    @callback
    def async_add_entity(event_type: EventType, resource: HueScene) -> None:
        """Add entity from Hue resource."""
        async_add_entities([HueSceneEntity(bridge, api.scenes, resource)])

    # add all current items in controller
    for item in api.scenes:
        async_add_entity(EventType.RESOURCE_ADDED, item)

    # register listener for new items only
    config_entry.async_on_unload(
        api.scenes.subscribe(async_add_entity, event_filter=EventType.RESOURCE_ADDED)
    )


class HueSceneEntity(HueBaseEntity, SceneEntity):
    """Representation of a Scene entity from Hue Scenes."""

    def __init__(
        self,
        bridge: HueBridge,
        controller: ScenesController,
        resource: HueScene,
    ) -> None:
        """Initialize the entity."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.controller = controller

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
        await self.bridge.async_request_call(
            self.controller.recall,
            self.resource.id,
            dynamic=dynamic,
            duration=transition,
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
            "group_name": group.metadata.name,
            "group_type": group.type.value,
            "name": self.resource.metadata.name,
            "speed": self.resource.speed,
            "brightness": brightness,
            "is_dynamic": self.is_dynamic,
        }
