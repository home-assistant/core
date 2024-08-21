"""Component providing support for ring events."""

from dataclasses import dataclass
from typing import Generic

from ring_doorbell import RingCapability, RingEvent as RingAlert
from ring_doorbell.const import KIND_DING, KIND_INTERCOM_UNLOCK, KIND_MOTION

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RingConfigEntry
from .coordinator import RingListenCoordinator
from .entity import RingBaseEntity, RingDeviceT


@dataclass(frozen=True, kw_only=True)
class RingEventEntityDescription(EventEntityDescription, Generic[RingDeviceT]):
    """Base class for event entity description."""

    capability: RingCapability


EVENT_DESCRIPTIONS: tuple[RingEventEntityDescription, ...] = (
    RingEventEntityDescription(
        key=KIND_DING,
        translation_key=KIND_DING,
        device_class=EventDeviceClass.DOORBELL,
        event_types=[KIND_DING],
        entity_registry_enabled_default=True,
        capability=RingCapability.DING,
    ),
    RingEventEntityDescription(
        key=KIND_MOTION,
        translation_key=KIND_MOTION,
        device_class=EventDeviceClass.MOTION,
        event_types=[KIND_MOTION],
        entity_registry_enabled_default=True,
        capability=RingCapability.MOTION_DETECTION,
    ),
    RingEventEntityDescription(
        key=KIND_INTERCOM_UNLOCK,
        translation_key=KIND_INTERCOM_UNLOCK,
        device_class=EventDeviceClass.BUTTON,
        event_types=[KIND_INTERCOM_UNLOCK],
        entity_registry_enabled_default=True,
        capability=RingCapability.OPEN,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a sensor for a Ring device."""
    ring_data = entry.runtime_data
    listen_coordinator = ring_data.listen_coordinator

    entities = [
        RingEvent(device, listen_coordinator, description)
        for description in EVENT_DESCRIPTIONS
        for device in ring_data.devices.all_devices
        if device.has_capability(description.capability)
    ]

    async_add_entities(entities)


class RingEvent(RingBaseEntity[RingListenCoordinator, RingDeviceT], EventEntity):
    """A sensor implementation for Ring device."""

    entity_description: RingEventEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingListenCoordinator,
        description: RingEventEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}-{description.key}"
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle the event."""
        self._trigger_event(event)

    def _get_coordinator_alert(self) -> RingAlert | None:
        alerts = (
            alert
            for alert in self.coordinator.ring_api.active_alerts()
            if alert.kind == self.entity_description.key
            and alert.doorbot_id == self._device.device_api_id
        )
        return next(alerts, None)

    @callback
    def _handle_coordinator_update(self) -> None:
        if alert := self._get_coordinator_alert():
            self._async_handle_event(alert.kind)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.event_listener.started

    async def async_update(self) -> None:
        """All updates are passive."""
