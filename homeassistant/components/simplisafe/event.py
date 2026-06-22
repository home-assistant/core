"""Support for SimpliSafe events."""

from typing import TYPE_CHECKING

from simplipy.device import Device
from simplipy.device.camera import CameraTypes
from simplipy.system.v3 import SystemV3
from simplipy.websocket import (
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DOORBELL_DETECTED,
    WebsocketEvent,
)

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT, SimpliSafe, SimpliSafeConfigEntry
from .entity import SimpliSafeEntity
from .typing import SystemType

CAMERA_DEVICE_EVENT_TYPES: dict[CameraTypes, list[str]] = {
    CameraTypes.CAMERA: [EVENT_CAMERA_MOTION_DETECTED],
    CameraTypes.OUTDOOR_CAMERA: [EVENT_CAMERA_MOTION_DETECTED],
    CameraTypes.DOORBELL: [EVENT_DOORBELL_DETECTED],
}

SYSTEM_EVENT_TYPES = [
    event
    for event in WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT
    if event not in (EVENT_CAMERA_MOTION_DETECTED, EVENT_DOORBELL_DETECTED)
]

CAMERA_DEVICE_CLASSES: dict[CameraTypes, EventDeviceClass] = {
    CameraTypes.CAMERA: EventDeviceClass.MOTION,
    CameraTypes.OUTDOOR_CAMERA: EventDeviceClass.MOTION,
    CameraTypes.DOORBELL: EventDeviceClass.DOORBELL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SimpliSafeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SimpliSafe events based on a config entry."""
    simplisafe = entry.runtime_data
    entities: list[SimpliSafeEvent] = []

    for system in simplisafe.systems.values():
        entities.append(
            SimpliSafeEvent(
                simplisafe,
                system,
                event_types=SYSTEM_EVENT_TYPES,
                translation_key="system_events",
                unique_id=f"{system.serial}-event",
            )
        )

        if not isinstance(system, SystemV3):
            continue

        if TYPE_CHECKING:
            assert isinstance(system, SystemV3)
        for uuid, camera in system.cameras.items():
            ws_serial = system.camera_data[uuid]["serial"]
            entities.append(
                SimpliSafeEvent(
                    simplisafe,
                    system,
                    device=camera,
                    ws_serial=ws_serial,
                    device_class=CAMERA_DEVICE_CLASSES.get(
                        camera.camera_type, EventDeviceClass.MOTION
                    ),
                    event_types=CAMERA_DEVICE_EVENT_TYPES.get(
                        camera.camera_type, [EVENT_CAMERA_MOTION_DETECTED]
                    ),
                    translation_key="camera_events",
                    unique_id=f"{camera.serial}-camera-event",
                )
            )

    async_add_entities(entities)


class SimpliSafeEvent(SimpliSafeEntity, EventEntity):
    """Define a SimpliSafe event entity."""

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemType,
        *,
        device: Device | None = None,
        device_class: EventDeviceClass | None = None,
        ws_serial: str | None = None,
        event_types: list[str],
        translation_key: str,
        unique_id: str,
    ) -> None:
        """Initialize."""
        self._attr_device_class = device_class
        self._attr_event_types = event_types
        self._attr_translation_key = translation_key
        self._ws_serial = ws_serial

        super().__init__(
            simplisafe,
            system,
            device=device,
            additional_websocket_events=event_types,
        )
        self._attr_unique_id = unique_id

    @callback
    def _handle_websocket_update(self, event: WebsocketEvent) -> None:
        """Update the entity with new websocket data."""
        if self._ws_serial and event.sensor_serial != self._ws_serial:
            return

        super()._handle_websocket_update(event)

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        assert event.event_type is not None
        event_attributes: dict[str, str | None] = {
            "changed_by": event.changed_by,
            "info": event.info,
        }
        if not self._ws_serial:
            event_attributes["sensor_name"] = event.sensor_name
            event_attributes["sensor_serial"] = event.sensor_serial
            event_attributes["sensor_type"] = (
                event.sensor_type.name if event.sensor_type else None
            )
        self._trigger_event(event.event_type, event_attributes=event_attributes)
