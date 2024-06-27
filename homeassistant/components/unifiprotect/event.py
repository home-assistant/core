"""Component providing binary sensors for UniFi Protect."""

from __future__ import annotations

import dataclasses

from uiprotect.data import Camera, ProtectAdoptableDeviceModel, ProtectModelWithId

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_EVENT_ID, ATTR_EVENT_SCORE
from .data import ProtectData, UFPConfigEntry
from .entity import EventEntityMixin, ProtectDeviceEntity
from .models import ProtectEventMixin


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectEventEntityDescription(ProtectEventMixin, EventEntityDescription):
    """Describes UniFi Protect event entity."""


EVENT_DESCRIPTIONS: tuple[ProtectEventEntityDescription, ...] = (
    ProtectEventEntityDescription(
        key="doorbell",
        name="Doorbell",
        device_class=EventDeviceClass.DOORBELL,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.is_doorbell",
        ufp_event_obj="last_ring_event",
    ),
)


class ProtectDeviceEventEntity(EventEntityMixin, ProtectDeviceEntity, EventEntity):
    """A UniFi Protect Device Binary Sensor for events."""

    entity_description: ProtectEventEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        description = self.entity_description

        prev_event = self._event
        prev_event_end = self._event_end
        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end if event else None

        if event and not self._event_already_ended(prev_event, prev_event_end):
            self._trigger_event(
                description.key,
                {
                    ATTR_EVENT_ID: event.id,
                    ATTR_EVENT_SCORE: event.score,
                },
            )


@callback
def _async_event_entities(
    data: ProtectData,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    for device in data.get_cameras() if ufp_device is None else [ufp_device]:
        return [
            ProtectDeviceEventEntity(data, device, description)
            for description in EVENT_DESCRIPTIONS
            if description.has_required(device)
        ]
    return []


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event entities for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if device.is_adopted and isinstance(device, Camera):
            async_add_entities(_async_event_entities(data, ufp_device=device))

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(_async_event_entities(data))
