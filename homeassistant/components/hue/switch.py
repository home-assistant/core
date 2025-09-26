"""Support for switch platform for Hue resources (V2 only)."""

from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.config import BehaviorInstance, BehaviorInstanceController
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import (
    LightLevel,
    LightLevelController,
    Motion,
    MotionController,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bridge import HueConfigEntry
from .v2.entity import HueBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue switch platform from Hue resources."""
    bridge = config_entry.runtime_data
    api: HueBridgeV2 = bridge.api

    if bridge.api_version == 1:
        # should not happen, but just in case
        raise NotImplementedError("Switch support is only available for V2 bridges")

    @callback
    def register_items(
        controller: BehaviorInstanceController
        | LightLevelController
        | MotionController,
        switch_class: type[
            HueBehaviorInstanceEnabledEntity
            | HueLightSensorEnabledEntity
            | HueMotionSensorEnabledEntity
        ],
    ):
        @callback
        def async_add_entity(
            event_type: EventType, resource: BehaviorInstance | LightLevel | Motion
        ) -> None:
            """Add entity from Hue resource."""
            async_add_entities([switch_class(bridge, controller, resource)])

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
    register_items(api.sensors.motion, HueMotionSensorEnabledEntity)
    register_items(api.sensors.light_level, HueLightSensorEnabledEntity)
    register_items(api.config.behavior_instance, HueBehaviorInstanceEnabledEntity)


class HueResourceEnabledEntity(HueBaseEntity, SwitchEntity):
    """Representation of a Switch entity from a Hue resource that can be toggled enabled."""

    controller: BehaviorInstanceController | LightLevelController | MotionController
    resource: BehaviorInstance | LightLevel | Motion

    entity_description = SwitchEntityDescription(
        key="sensing_service_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
    )

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


class HueBehaviorInstanceEnabledEntity(HueResourceEnabledEntity):
    """Representation of a Switch entity to enable/disable a Hue Behavior Instance."""

    resource: BehaviorInstance

    entity_description = SwitchEntityDescription(
        key="behavior_instance",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=False,
    )

    @property
    def name(self) -> str:
        """Return name for this entity."""
        return f"Automation: {self.resource.metadata.name}"


class HueMotionSensorEnabledEntity(HueResourceEnabledEntity):
    """Representation of a Switch entity to enable/disable a Hue motion sensor."""

    entity_description = SwitchEntityDescription(
        key="motion_sensor_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        translation_key="motion_sensor_enabled",
    )


class HueLightSensorEnabledEntity(HueResourceEnabledEntity):
    """Representation of a Switch entity to enable/disable a Hue light sensor."""

    entity_description = SwitchEntityDescription(
        key="light_sensor_enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        translation_key="light_sensor_enabled",
    )
