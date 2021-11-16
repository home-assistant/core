"""Support for switch platform for Hue resources (V2 only)."""
from __future__ import annotations

from typing import Any, Union

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import LightLevelController, MotionController
from aiohue.v2.models.resource import SensingService

from homeassistant.components.switch import DEVICE_CLASS_SWITCH, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import HueBridge
from .const import DOMAIN
from .v2.entity import HueBaseEntity

ControllerType = Union[LightLevelController, MotionController]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue switch platform from Hue resources."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    if bridge.api_version == 1:
        # should not happen, but just in case
        raise NotImplementedError("Switch support is only available for V2 bridges")

    @callback
    def register_items(controller: ControllerType):
        @callback
        def async_add_entity(event_type: EventType, resource: SensingService) -> None:
            """Add entity from Hue resource."""
            async_add_entities(
                [HueSensingServiceEnabledEntity(bridge, controller, resource)]
            )

        # add all current items in controller
        for item in controller:
            async_add_entity(EventType.RESOURCE_ADDED, item)

        # register listener for new items only
        config_entry.async_on_unload(
            controller.subscribe(
                async_add_entity, event_filter=EventType.RESOURCE_ADDED
            )
        )

    # setup for each switch-type hue resource
    register_items(api.sensors.motion)
    register_items(api.sensors.light_level)


class HueSensingServiceEnabledEntity(HueBaseEntity, SwitchEntity):
    """Representation of a Switch entity from Hue SensingService."""

    _attr_entity_category = ENTITY_CATEGORY_CONFIG
    _attr_device_class = DEVICE_CLASS_SWITCH

    def __init__(
        self,
        bridge: HueBridge,
        controller: LightLevelController | MotionController,
        resource: SensingService,
    ) -> None:
        """Initialize the entity."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.controller = controller

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.resource.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.bridge.async_request_call(
            self.controller.set_enabled, self.resource.id, enabled=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.bridge.async_request_call(
            self.controller.set_enabled, self.resource.id, enabled=False
        )
