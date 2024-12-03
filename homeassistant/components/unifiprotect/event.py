"""Platform providing event entities for UniFi Protect."""

from __future__ import annotations

import dataclasses

from uiprotect.data import Camera, EventType, ProtectAdoptableDeviceModel

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_EVENT_ID,
    EVENT_TYPE_DOORBELL_RING,
    EVENT_TYPE_FINGERPRINT_IDENTIFIED,
    EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED,
    EVENT_TYPE_NFC_SCANNED,
)
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import EventEntityMixin, ProtectDeviceEntity, ProtectEventMixin


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectEventEntityDescription(ProtectEventMixin, EventEntityDescription):
    """Describes UniFi Protect event entity."""

    entity_class: type[ProtectDeviceEntity]


class ProtectDeviceRingEventEntity(EventEntityMixin, ProtectDeviceEntity, EventEntity):
    """A UniFi Protect event entity."""

    entity_description: ProtectEventEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        description = self.entity_description

        prev_event = self._event
        prev_event_end = self._event_end
        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end if event else None

        if (
            event
            and not self._event_already_ended(prev_event, prev_event_end)
            and event.type is EventType.RING
        ):
            self._trigger_event(EVENT_TYPE_DOORBELL_RING, {ATTR_EVENT_ID: event.id})
            self.async_write_ha_state()


class ProtectDeviceNFCEventEntity(EventEntityMixin, ProtectDeviceEntity, EventEntity):
    """A UniFi Protect NFC event entity."""

    entity_description: ProtectEventEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        description = self.entity_description

        prev_event = self._event
        prev_event_end = self._event_end
        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end if event else None

        if (
            event
            and not self._event_already_ended(prev_event, prev_event_end)
            and event.type is EventType.NFC_CARD_SCANNED
        ):
            event_data = {ATTR_EVENT_ID: event.id}
            if event.metadata and event.metadata.nfc and event.metadata.nfc.nfc_id:
                event_data["nfc_id"] = event.metadata.nfc.nfc_id

            self._trigger_event(EVENT_TYPE_NFC_SCANNED, event_data)
            self.async_write_ha_state()


class ProtectDeviceFingerprintEventEntity(
    EventEntityMixin, ProtectDeviceEntity, EventEntity
):
    """A UniFi Protect fingerprint event entity."""

    entity_description: ProtectEventEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        description = self.entity_description

        prev_event = self._event
        prev_event_end = self._event_end
        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end if event else None

        if (
            event
            and not self._event_already_ended(prev_event, prev_event_end)
            and event.type is EventType.FINGERPRINT_IDENTIFIED
        ):
            event_data = {ATTR_EVENT_ID: event.id}
            if (
                event.metadata
                and event.metadata.fingerprint
                and event.metadata.fingerprint.ulp_id
            ):
                event_data["ulp_id"] = event.metadata.fingerprint.ulp_id
                event_identified = EVENT_TYPE_FINGERPRINT_IDENTIFIED
            else:
                event_data["ulp_id"] = ""
                event_identified = EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED

            self._trigger_event(event_identified, event_data)
            self.async_write_ha_state()


EVENT_DESCRIPTIONS: tuple[ProtectEventEntityDescription, ...] = (
    ProtectEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.is_doorbell",
        ufp_event_obj="last_ring_event",
        event_types=[EVENT_TYPE_DOORBELL_RING],
        entity_class=ProtectDeviceRingEventEntity,
    ),
    ProtectEventEntityDescription(
        key="nfc",
        translation_key="nfc",
        device_class=EventDeviceClass.DOORBELL,
        icon="mdi:nfc",
        ufp_required_field="feature_flags.support_nfc",
        ufp_event_obj="last_nfc_card_scanned_event",
        event_types=[EVENT_TYPE_NFC_SCANNED],
        entity_class=ProtectDeviceNFCEventEntity,
    ),
    ProtectEventEntityDescription(
        key="fingerprint",
        translation_key="fingerprint",
        device_class=EventDeviceClass.DOORBELL,
        icon="mdi:fingerprint",
        ufp_required_field="feature_flags.has_fingerprint_sensor",
        ufp_event_obj="last_fingerprint_identified_event",
        event_types=[
            EVENT_TYPE_FINGERPRINT_IDENTIFIED,
            EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED,
        ],
        entity_class=ProtectDeviceFingerprintEventEntity,
    ),
)


@callback
def _async_event_entities(
    data: ProtectData,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    return [
        description.entity_class(data, device, description)
        for device in (data.get_cameras() if ufp_device is None else [ufp_device])
        for description in EVENT_DESCRIPTIONS
        if description.has_required(device)
    ]


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
