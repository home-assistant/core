"""Support for scene platform for Hue scenes (V2 only)."""
from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.scenes import ScenesController
from aiohue.v2.models.scene import Scene as HueScene, ScenePut as HueScenePut
from aiohue.v2.models.smart_scene import SmartScene as HueSmartScene, SmartSceneState
import voluptuous as vol

from homeassistant.components.scene import ATTR_TRANSITION, Scene as SceneEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .bridge import HueBridge
from .const import DOMAIN
from .v2.entity import HueBaseEntity
from .v2.helpers import normalize_hue_brightness, normalize_hue_transition

SERVICE_ACTIVATE_SCENE = "activate_scene"
ATTR_DYNAMIC = "dynamic"
ATTR_SPEED = "speed"
ATTR_BRIGHTNESS = "brightness"


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
    def async_add_entity(
        event_type: EventType, resource: HueScene | HueSmartScene
    ) -> None:
        """Add entity from Hue resource."""
        if isinstance(resource, HueSmartScene):
            async_add_entities([HueSmartSceneEntity(bridge, api.scenes, resource)])
        else:
            async_add_entities([HueSceneEntity(bridge, api.scenes, resource)])

    # add all current items in controller
    for item in api.scenes:
        async_add_entity(EventType.RESOURCE_ADDED, item)

    # register listener for new items only
    config_entry.async_on_unload(
        api.scenes.subscribe(async_add_entity, event_filter=EventType.RESOURCE_ADDED)
    )

    # add platform service to turn_on/activate scene with advanced options
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ACTIVATE_SCENE,
        {
            vol.Optional(ATTR_DYNAMIC): vol.Coerce(bool),
            vol.Optional(ATTR_SPEED): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(ATTR_TRANSITION): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=3600)
            ),
            vol.Optional(ATTR_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
        },
        "_async_activate",
    )


class HueSceneEntityBase(HueBaseEntity, SceneEntity):
    """Base Representation of a Scene entity from Hue Scenes."""

    def __init__(
        self,
        bridge: HueBridge,
        controller: ScenesController,
        resource: HueScene | HueSmartScene,
    ) -> None:
        """Initialize the entity."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.controller = controller
        self.group = self.controller.get_group(self.resource.id)

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        # Add value_changed callback for group to catch name changes.
        self.async_on_remove(
            self.bridge.api.groups.subscribe(
                self._handle_event,
                self.group.id,
                (EventType.RESOURCE_UPDATED),
            )
        )

    @property
    def name(self) -> str:
        """Return default entity name."""
        return f"{self.group.metadata.name} {self.resource.metadata.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device (service) info."""
        # we create a virtual service/device for Hue scenes
        # so we have a parent for grouped lights and scenes
        group_type = self.group.type.value.title()
        return DeviceInfo(
            identifiers={(DOMAIN, self.group.id)},
            entry_type=DeviceEntryType.SERVICE,
            name=self.group.metadata.name,
            manufacturer=self.bridge.api.config.bridge_device.product_data.manufacturer_name,
            model=self.group.type.value.title(),
            suggested_area=self.group.metadata.name if group_type == "Room" else None,
            via_device=(DOMAIN, self.bridge.api.config.bridge_device.id),
        )


class HueSceneEntity(HueSceneEntityBase):
    """Representation of a Scene entity from Hue Scenes."""

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
        transition = normalize_hue_transition(kwargs.get(ATTR_TRANSITION))
        # the options below are advanced only
        # as we're not allowed to override the default scene turn_on service
        # we've implemented a `activate_scene` entity service
        dynamic = kwargs.get(ATTR_DYNAMIC, False)
        speed = kwargs.get(ATTR_SPEED)
        brightness = normalize_hue_brightness(kwargs.get(ATTR_BRIGHTNESS))

        if speed is not None:
            await self.bridge.async_request_call(
                self.controller.scene.update,
                self.resource.id,
                HueScenePut(speed=speed / 100),
            )

        await self.bridge.async_request_call(
            self.controller.scene.recall,
            self.resource.id,
            dynamic=dynamic,
            duration=transition,
            brightness=brightness,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
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
            "group_name": self.group.metadata.name,
            "group_type": self.group.type.value,
            "name": self.resource.metadata.name,
            "speed": self.resource.speed,
            "brightness": brightness,
            "is_dynamic": self.is_dynamic,
        }


class HueSmartSceneEntity(HueSceneEntityBase):
    """Representation of a Smart Scene entity from Hue Scenes."""

    @property
    def is_active(self) -> bool:
        """Return if this smart scene is currently active."""
        return self.resource.state == SmartSceneState.ACTIVE

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate Hue Smart scene."""

        await self.bridge.async_request_call(
            self.controller.smart_scene.recall,
            self.resource.id,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        res = {
            "group_name": self.group.metadata.name,
            "group_type": self.group.type.value,
            "name": self.resource.metadata.name,
            "is_active": self.is_active,
        }
        if self.is_active and self.resource.active_timeslot:
            res["active_timeslot_id"] = self.resource.active_timeslot.timeslot_id
            res["active_timeslot_name"] = self.resource.active_timeslot.weekday.value
            # lookup active scene in timeslot
            active_scene = None
            count = 0
            for day_timeslot in self.resource.week_timeslots:
                for timeslot in day_timeslot.timeslots:
                    if count != self.resource.active_timeslot.timeslot_id:
                        count += 1
                        continue
                    active_scene = self.controller.get(timeslot.target.rid)
                    break
            if active_scene is not None:
                res["active_scene"] = active_scene.metadata.name
        return res
