"""Platform providing event entities for UniFi Protect."""

from __future__ import annotations

import dataclasses
from typing import Any

from uiprotect.data.nvr import Event, EventDetectedThumbnail

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_at

from . import Bootstrap
from .const import (
    ATTR_EVENT_ID,
    EVENT_TYPE_DOORBELL_RING,
    EVENT_TYPE_FINGERPRINT_IDENTIFIED,
    EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED,
    EVENT_TYPE_NFC_SCANNED,
    EVENT_TYPE_VEHICLE_DETECTED,
    KEYRINGS_KEY_TYPE_ID_NFC,
    KEYRINGS_ULP_ID,
    KEYRINGS_USER_FULL_NAME,
    KEYRINGS_USER_STATUS,
    VEHICLE_EVENT_DELAY_SECONDS,
)
from .data import (
    Camera,
    EventType,
    ProtectAdoptableDeviceModel,
    ProtectData,
    ProtectDeviceType,
    UFPConfigEntry,
)
from .entity import EventEntityMixin, ProtectDeviceEntity, ProtectEventMixin

PARALLEL_UPDATES = 0


# Select best thumbnail
# Prefer thumbnails with LPR data, sorted by confidence
# LPR can be in: 1) group.matched_name (UFP 6.0+) or 2) name field
def _thumbnail_sort_key(t: EventDetectedThumbnail) -> tuple[bool, float, float]:
    """Sort key: (has_lpr, confidence, clock_best_wall)."""
    has_lpr = bool((t.group and t.group.matched_name) or (t.name and len(t.name) > 0))
    confidence = t.confidence if t.confidence else 0.0
    clock = t.clock_best_wall.timestamp() if t.clock_best_wall else 0.0
    return (has_lpr, confidence, clock)


def _add_ulp_user_infos(
    bootstrap: Bootstrap, event_data: dict[str, str], ulp_id: str
) -> None:
    """Add ULP user information to the event data."""
    if ulp_usr := bootstrap.ulp_users.by_ulp_id(ulp_id):
        event_data.update(
            {
                KEYRINGS_ULP_ID: ulp_usr.ulp_id,
                KEYRINGS_USER_FULL_NAME: ulp_usr.full_name,
                KEYRINGS_USER_STATUS: ulp_usr.status,
            }
        )


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
            event_data = {
                ATTR_EVENT_ID: event.id,
                KEYRINGS_USER_FULL_NAME: "",
                KEYRINGS_ULP_ID: "",
                KEYRINGS_USER_STATUS: "",
                KEYRINGS_KEY_TYPE_ID_NFC: "",
            }

            if event.metadata and event.metadata.nfc and event.metadata.nfc.nfc_id:
                nfc_id = event.metadata.nfc.nfc_id
                event_data[KEYRINGS_KEY_TYPE_ID_NFC] = nfc_id
                keyring = self.data.api.bootstrap.keyrings.by_registry_id(nfc_id)
                if keyring and keyring.ulp_user:
                    _add_ulp_user_infos(
                        self.data.api.bootstrap, event_data, keyring.ulp_user
                    )

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
            event_data = {
                ATTR_EVENT_ID: event.id,
                KEYRINGS_USER_FULL_NAME: "",
                KEYRINGS_ULP_ID: "",
            }
            event_identified = EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED
            if (
                event.metadata
                and event.metadata.fingerprint
                and event.metadata.fingerprint.ulp_id
            ):
                event_identified = EVENT_TYPE_FINGERPRINT_IDENTIFIED
                ulp_id = event.metadata.fingerprint.ulp_id
                if ulp_id:
                    event_data[KEYRINGS_ULP_ID] = ulp_id
                    _add_ulp_user_infos(self.data.api.bootstrap, event_data, ulp_id)

            self._trigger_event(event_identified, event_data)
            self.async_write_ha_state()


class ProtectDeviceVehicleEventEntity(
    EventEntityMixin, ProtectDeviceEntity, EventEntity
):
    """A UniFi Protect vehicle detection event entity.

    Vehicle detection events use a delayed firing mechanism to allow time for
    the best thumbnail (with license plate recognition data) to arrive. The
    timer is extended each time new thumbnails arrive for the same event. If
    a new event arrives while a timer is pending, the old event fires immediately
    with its stored thumbnails, then a new timer starts for the new event.
    """

    entity_description: ProtectEventEntityDescription
    _thumbnail_timer_cancel: CALLBACK_TYPE | None = None
    _latest_event_id: str | None = None
    _latest_thumbnails: list[EventDetectedThumbnail] | None = None
    _thumbnail_timer_due: float = 0.0  # Loop time when timer should fire
    _fired_event_id: str | None = None  # Track last fired event to prevent duplicates
    _fired_event_data: dict[str, Any] | None = None  # Track event data when fired

    async def async_added_to_hass(self) -> None:
        """Register cleanup callback when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_thumbnail_timer)

    @callback
    def _cancel_thumbnail_timer(self) -> None:
        """Cancel pending thumbnail timer if one exists."""
        if self._thumbnail_timer_cancel:
            self._thumbnail_timer_cancel()
            self._thumbnail_timer_cancel = None

    @callback
    def _async_timer_callback(self, *_: Any) -> None:
        """Handle timer expiration - fire the vehicle event.

        If the due time was extended (new thumbnails arrived), re-arm the timer.
        Otherwise, fire the event with the stored thumbnails.
        """
        self._thumbnail_timer_cancel = None
        if self._thumbnail_timer_due > self.hass.loop.time():
            # Timer fired early because due time was extended; re-arm
            self._async_set_thumbnail_timer()
            return

        if self._latest_event_id:
            self._fire_vehicle_event(self._latest_event_id, self._latest_thumbnails)

    @staticmethod
    def _get_vehicle_thumbnails(event: Event) -> list[EventDetectedThumbnail]:
        """Get vehicle thumbnails from event."""
        if event.metadata and event.metadata.detected_thumbnails:
            return [
                t for t in event.metadata.detected_thumbnails if t.type == "vehicle"
            ]
        return []

    @staticmethod
    def _build_event_data(
        event_id: str, thumbnails: list[EventDetectedThumbnail]
    ) -> dict[str, Any]:
        """Build event data dictionary from thumbnails."""
        event_data: dict[str, Any] = {
            ATTR_EVENT_ID: event_id,
            "thumbnail_count": len(thumbnails),
        }

        thumbnail = max(thumbnails, key=_thumbnail_sort_key)

        # Add confidence if available
        if thumbnail.confidence is not None:
            event_data["confidence"] = thumbnail.confidence

        # Add best detection frame timestamp
        if thumbnail.clock_best_wall is not None:
            event_data["clock_best_wall"] = thumbnail.clock_best_wall.isoformat()

        # License plate from group.matched_name (UFP 6.0+) or name field (older)
        if thumbnail.group and thumbnail.group.matched_name:
            event_data["license_plate"] = thumbnail.group.matched_name
        elif thumbnail.name:
            event_data["license_plate"] = thumbnail.name

        # Add all thumbnail attributes as dict
        if thumbnail.attributes:
            event_data["attributes"] = thumbnail.attributes.unifi_dict()

        return event_data

    @callback
    def _fire_vehicle_event(
        self, event_id: str, thumbnails: list[EventDetectedThumbnail] | None = None
    ) -> None:
        """Fire the vehicle detection event with best available thumbnail.

        Args:
            event_id: The event ID to include in the fired event data.
            thumbnails: Pre-stored thumbnails to use. If None, fetches from
                the current event (used when event is still active).
        """
        if thumbnails is None:
            # No stored thumbnails; try to get from current event
            event = self.entity_description.get_event_obj(self.device)
            if not event or event.id != event_id:
                return
            thumbnails = self._get_vehicle_thumbnails(event)

        if not thumbnails:
            return

        event_data = self._build_event_data(event_id, thumbnails)

        # Prevent duplicate firing of same event with same data
        if self._fired_event_id == event_id and self._fired_event_data == event_data:
            return

        # Mark this event as fired with its data
        self._fired_event_id = event_id
        self._fired_event_data = event_data

        self._trigger_event(EVENT_TYPE_VEHICLE_DETECTED, event_data)
        self.async_write_ha_state()

    @callback
    def _async_set_thumbnail_timer(self) -> None:
        """Schedule the thumbnail timer to fire at _thumbnail_timer_due."""
        self._thumbnail_timer_cancel = async_call_at(
            self.hass,
            self._async_timer_callback,
            self._thumbnail_timer_due,
        )

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        description = self.entity_description

        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end if event else None

        # Process vehicle detection events with thumbnails
        if (
            event
            and event.type is EventType.SMART_DETECT
            and (thumbnails := self._get_vehicle_thumbnails(event))
        ):
            # Skip if same event with same data (no changes)
            if (
                self._fired_event_id == event.id
                and self._fired_event_data
                == self._build_event_data(event.id, thumbnails)
            ):
                return

            # New event arrived while timer pending for different event?
            # Fire the old event immediately since it has completed
            if self._latest_event_id and self._latest_event_id != event.id:
                # Only fire if we haven't already (shouldn't happen, but defensive)
                self._fire_vehicle_event(self._latest_event_id, self._latest_thumbnails)
                self._cancel_thumbnail_timer()

            # Store event data and extend/start the timer
            # Timer extension allows better thumbnails (with LPR) to arrive
            self._latest_event_id = event.id
            self._latest_thumbnails = thumbnails
            self._thumbnail_timer_due = (
                self.hass.loop.time() + VEHICLE_EVENT_DELAY_SECONDS
            )
            # Only schedule if no timer running; existing timer will re-arm
            if self._thumbnail_timer_cancel is None:
                self._async_set_thumbnail_timer()


EVENT_DESCRIPTIONS: tuple[ProtectEventEntityDescription, ...] = (
    ProtectEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        ufp_required_field="feature_flags.is_doorbell",
        ufp_event_obj="last_ring_event",
        event_types=[EVENT_TYPE_DOORBELL_RING],
        entity_class=ProtectDeviceRingEventEntity,
    ),
    ProtectEventEntityDescription(
        key="nfc",
        translation_key="nfc",
        ufp_required_field="feature_flags.support_nfc",
        ufp_event_obj="last_nfc_card_scanned_event",
        event_types=[EVENT_TYPE_NFC_SCANNED],
        entity_class=ProtectDeviceNFCEventEntity,
    ),
    ProtectEventEntityDescription(
        key="fingerprint",
        translation_key="fingerprint",
        ufp_required_field="feature_flags.has_fingerprint_sensor",
        ufp_event_obj="last_fingerprint_identified_event",
        event_types=[
            EVENT_TYPE_FINGERPRINT_IDENTIFIED,
            EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED,
        ],
        entity_class=ProtectDeviceFingerprintEventEntity,
    ),
    ProtectEventEntityDescription(
        key="vehicle",
        translation_key="vehicle",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_detect_event",
        event_types=[EVENT_TYPE_VEHICLE_DETECTED],
        entity_class=ProtectDeviceVehicleEventEntity,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event entities for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if device.is_adopted and isinstance(device, Camera):
            async_add_entities(_async_event_entities(data, ufp_device=device))

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(_async_event_entities(data))
