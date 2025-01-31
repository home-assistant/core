"""Component providing support for ring events."""

from dataclasses import dataclass
from typing import Any

from ring_doorbell import RingCapability, RingEvent as RingAlert, RingGeneric
from ring_doorbell.const import KIND_DING, KIND_INTERCOM_UNLOCK, KIND_MOTION

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RingConfigEntry
from .entity import RingDeviceT, RingEntityDescription, RingListenEntity

# Event entity does not perform updates or actions.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RingEventEntityDescription(
    EventEntityDescription, RingEntityDescription[RingGeneric]
):
    """Base class for event entity description."""


EVENT_DESCRIPTIONS: tuple[RingEntityDescription[Any], ...] = (
    RingEventEntityDescription(
        key=KIND_DING,
        translation_key=KIND_DING,
        device_class=EventDeviceClass.DOORBELL,
        event_types=[KIND_DING],
        exists_fn=lambda device: device.has_capability(RingCapability.DING),
    ),
    RingEventEntityDescription(
        key=KIND_MOTION,
        translation_key=KIND_MOTION,
        device_class=EventDeviceClass.MOTION,
        event_types=[KIND_MOTION],
        exists_fn=lambda device: device.has_capability(RingCapability.MOTION_DETECTION),
    ),
    RingEventEntityDescription(
        key=KIND_INTERCOM_UNLOCK,
        translation_key=KIND_INTERCOM_UNLOCK,
        device_class=EventDeviceClass.BUTTON,
        event_types=[KIND_INTERCOM_UNLOCK],
        exists_fn=lambda device: device.has_capability(RingCapability.OPEN),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up events for a Ring device."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator
    listen_coordinator = ring_data.listen_coordinator

    RingEvent.process_entities(
        hass,
        devices_coordinator,
        listen_coordinator,
        async_add_entities=async_add_entities,
        domain=EVENT_DOMAIN,
        descriptions=EVENT_DESCRIPTIONS,
    )


class RingEvent(RingListenEntity[RingDeviceT], EventEntity):
    """An event implementation for Ring device."""

    entity_description: RingEventEntityDescription

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle the event."""
        self._trigger_event(event)

    def _get_coordinator_alert(self) -> RingAlert | None:
        return self.coordinator.alerts.get(
            (self._device.device_api_id, self.entity_description.key)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        if (alert := self._get_coordinator_alert()) and not alert.is_update:
            self._async_handle_event(alert.kind)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.event_listener.started

    async def async_update(self) -> None:
        """All updates are passive."""
