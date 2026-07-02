"""Support for SimpliSafe events."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simplipy.device import Device
from simplipy.device.camera import CameraTypes
from simplipy.system.v3 import SystemV3
from simplipy.websocket import (
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DOORBELL_DETECTED,
    WebsocketEvent,
)

from homeassistant.components.event import (
    DoorbellEventType,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT, SimpliSafe, SimpliSafeConfigEntry
from .entity import SimpliSafeEntity
from .typing import SystemType

SYSTEM_EVENT_TYPES = [
    event
    for event in WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT
    if event not in (EVENT_CAMERA_MOTION_DETECTED, EVENT_DOORBELL_DETECTED)
]


@dataclass(frozen=True, kw_only=True)
class SimpliSafeCameraEventDescription(EventEntityDescription):
    """Describe a SimpliSafe camera event entity."""

    raw_event_type: str


CAMERA_EVENT_DESCRIPTIONS: dict[CameraTypes, list[SimpliSafeCameraEventDescription]] = {
    CameraTypes.CAMERA: [
        SimpliSafeCameraEventDescription(
            key="motion",
            device_class=EventDeviceClass.MOTION,
            event_types=[EVENT_CAMERA_MOTION_DETECTED],
            raw_event_type=EVENT_CAMERA_MOTION_DETECTED,
        ),
    ],
    CameraTypes.OUTDOOR_CAMERA: [
        SimpliSafeCameraEventDescription(
            key="motion",
            device_class=EventDeviceClass.MOTION,
            event_types=[EVENT_CAMERA_MOTION_DETECTED],
            raw_event_type=EVENT_CAMERA_MOTION_DETECTED,
        ),
    ],
    CameraTypes.DOORBELL: [
        SimpliSafeCameraEventDescription(
            key="ring",
            device_class=EventDeviceClass.DOORBELL,
            event_types=[DoorbellEventType.RING],
            raw_event_type=EVENT_DOORBELL_DETECTED,
        ),
        SimpliSafeCameraEventDescription(
            key="motion",
            device_class=EventDeviceClass.MOTION,
            event_types=[EVENT_CAMERA_MOTION_DETECTED],
            raw_event_type=EVENT_CAMERA_MOTION_DETECTED,
        ),
    ],
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
                entity_description=EventEntityDescription(
                    key="system_events",
                    event_types=SYSTEM_EVENT_TYPES,
                ),
                unique_id=f"{system.serial}-system_events",
            )
        )

        if not isinstance(system, SystemV3):
            continue

        if TYPE_CHECKING:
            assert isinstance(system, SystemV3)
        for uuid, camera in system.cameras.items():
            ws_serial = system.camera_data[uuid]["serial"]
            entities.extend(
                SimpliSafeEvent(
                    simplisafe,
                    system,
                    entity_description=description,
                    device=camera,
                    ws_serial=ws_serial,
                    unique_id=f"{camera.serial}-{description.key}",
                )
                for description in CAMERA_EVENT_DESCRIPTIONS.get(
                    camera.camera_type, CAMERA_EVENT_DESCRIPTIONS[CameraTypes.CAMERA]
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
        entity_description: EventEntityDescription,
        device: Device | None = None,
        ws_serial: str | None = None,
        unique_id: str,
    ) -> None:
        """Initialize."""
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._ws_serial = ws_serial

        super().__init__(
            simplisafe,
            system,
            device=device,
            additional_websocket_events=(
                [entity_description.raw_event_type]
                if isinstance(entity_description, SimpliSafeCameraEventDescription)
                else entity_description.event_types
            ),
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
        self._trigger_event(
            DoorbellEventType.RING
            if event.event_type == EVENT_DOORBELL_DETECTED
            else event.event_type,
            event_attributes=event_attributes,
        )
