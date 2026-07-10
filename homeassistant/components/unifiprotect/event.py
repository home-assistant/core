"""Platform providing event entities for UniFi Protect."""

import dataclasses
import re
from typing import Any, override

from uiprotect import ProtectEvent
from uiprotect.data import ModelType, SmartDetectObjectType
from uiprotect.data.nvr import Event, EventDetectedThumbnail

from homeassistant.components.event import (
    DoorbellEventType,
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
    ATTR_SMART_DETECT_TYPES,
    EVENT_TYPE_FINGERPRINT_IDENTIFIED,
    EVENT_TYPE_FINGERPRINT_NOT_IDENTIFIED,
    EVENT_TYPE_NFC_SCANNED,
    EVENT_TYPE_PACKAGE_DETECTED,
    EVENT_TYPE_VEHICLE_DETECTED,
    KEYRINGS_KEY_TYPE_ID_NFC,
    KEYRINGS_ULP_ID,
    KEYRINGS_USER_FULL_NAME,
    KEYRINGS_USER_STATUS,
    VEHICLE_EVENT_DELAY_SECONDS,
)
from .data import (
    EventType,
    ProtectAdoptableDeviceModel,
    ProtectData,
    ProtectDeviceType,
    UFPConfigEntry,
)
from .entity import EventEntityMixin, ProtectDeviceEntity, ProtectEventMixin

PARALLEL_UPDATES = 0

# Per-entity cap on tracked event ids for fire dedup (far above realistic
# concurrent/recent events per camera per category).
_MAX_TRACKED_EVENTS = 16


# Select best thumbnail
# Prefer thumbnails with LPR data, sorted by confidence
# LPR can be in: 1) group.matched_name (UFP 6.0+) or 2) name field
def _thumbnail_sort_key(t: EventDetectedThumbnail) -> tuple[bool, float, float]:
    """Sort key: (has_lpr, confidence, clock_best_wall)."""
    has_lpr = bool((t.group and t.group.matched_name) or (t.name and len(t.name) > 0))
    confidence = t.confidence or 0.0
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


# Protect emits overlapping ``smartDetectZone`` and ``smartDetectLine`` frames,
# and a line-crossing detection can arrive as a standalone ``smartDetectLine``
# event — both types carry smart detections (mirroring the private
# ``CAMERA_EVENT_ATTR_MAP``), so smart-detect entities subscribe to both.
_SMART_DETECT_EVENT_TYPES = (EventType.SMART_DETECT, EventType.SMART_DETECT_LINE)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectDetectionEventEntityDescription(ProtectEventEntityDescription):
    """Describes a category detection event entity driven by the public events WS."""

    ufp_public_event_types: tuple[EventType, ...]


class ProtectDevicePublicEventEntity(
    EventEntityMixin, ProtectDeviceEntity, EventEntity
):
    """Base for entities driven by the public events WS.

    A detection type can surface at the event start, on a later update, or only
    as the event ends, and every non-eviction change is dispatched — so firing is
    deduped per ``(event id, event type)``.

    Availability follows the public API (device present and connected) plus the
    events websocket, which is the only channel these entities fire from.
    """

    _ufp_uses_public = True
    _ufp_requires_events_ws = True

    entity_description: ProtectEventEntityDescription
    # A camera can run two overlapping events of the same category whose
    # dispatches interleave, so dedup tracks fired types per recent event id
    # (bounded), not just the current one.
    _fired: dict[str, frozenset[str]] | None = None

    @callback
    def _fire_once(
        self, event: ProtectEvent, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """Fire ``event_type`` once per event, ignoring repeat dispatches."""
        fired = self._fired
        if fired is None:
            fired = self._fired = {}
        # Pop-and-reinsert so any dispatch refreshes this event id's recency; a
        # long-running event that keeps updating is then not evicted below.
        types = fired.pop(event.id, frozenset())
        if event_type in types:
            fired[event.id] = types
            return
        fired[event.id] = types | {event_type}
        if len(fired) > _MAX_TRACKED_EVENTS:
            del fired[next(iter(fired))]  # evict the least-recently-seen event id
        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()


class ProtectDeviceRingEventEntity(ProtectDevicePublicEventEntity):
    """A UniFi Protect doorbell ring event entity driven by the public events WS."""

    entity_description: ProtectEventEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to public ring events for this doorbell."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe_public_event(
                self.device.id, EventType.RING, self._async_ring_event
            )
        )

    @callback
    def _async_ring_event(self, event: ProtectEvent) -> None:
        self._fire_once(event, DoorbellEventType.RING, {ATTR_EVENT_ID: event.id})


class ProtectDeviceNFCEventEntity(EventEntityMixin, ProtectDeviceEntity, EventEntity):
    """A UniFi Protect NFC event entity."""

    entity_description: ProtectEventEntityDescription

    @callback
    @override
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
    @override
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

    @override
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
    @override
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


class ProtectDeviceSmartDetectEventEntity(ProtectDevicePublicEventEntity):
    """A UniFi Protect smart-detect event entity driven by the public events WS.

    Used for object types that Protect models as discrete, point-in-time
    detections (e.g. package): the camera fires once with a cooldown and the
    smart-detect event is recorded already-ended, so a sustained binary sensor
    can never reflect it. The public events websocket delivers these as proper
    ``smartDetectZone`` events (the private API only exposes the unhandled
    ``smartDetectObject`` model), so we subscribe there and fire a momentary
    event when the description's object type matches.
    """

    entity_description: ProtectEventEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to public smart-detect events for this camera."""
        await super().async_added_to_hass()
        for event_type in _SMART_DETECT_EVENT_TYPES:
            self.async_on_remove(
                self.data.async_subscribe_public_event(
                    self.device.id, event_type, self._async_smart_detect_event
                )
            )

    @callback
    def _async_smart_detect_event(self, event: ProtectEvent) -> None:
        description = self.entity_description
        event_types = description.event_types
        if event_types and description.ufp_obj_type in event.smart_detect_types:
            self._fire_once(event, event_types[0], {ATTR_EVENT_ID: event.id})


_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")

# Friendly event-type slugs where the raw enum value is unclear or prefixed;
# unlisted types fall back to a snake_case slug so new ones still auto-surface.
_EVENT_TYPE_OVERRIDES = {
    SmartDetectObjectType.SMOKE: "smoke",
    SmartDetectObjectType.CMONX: "co",
    SmartDetectObjectType.SIREN: "siren",
    SmartDetectObjectType.BABY_CRY: "baby_cry",
    SmartDetectObjectType.SPEAK: "speaking",
    SmartDetectObjectType.BARK: "bark",
    SmartDetectObjectType.BURGLAR: "car_alarm",
    SmartDetectObjectType.CAR_HORN: "car_horn",
    SmartDetectObjectType.GLASS_BREAK: "glass_break",
}


def _event_type(detected: SmartDetectObjectType) -> str:
    """Stable snake_case event type for a detection (HA translation-key rules)."""
    return (
        _EVENT_TYPE_OVERRIDES.get(detected)
        or _CAMEL_BOUNDARY.sub("_", detected.value).lower()
    )


_SMART_OBJECT_EVENT_TYPES = [
    _event_type(t) for t in SmartDetectObjectType if t.audio_type is None
]
_SMART_AUDIO_EVENT_TYPES = [
    _event_type(t) for t in SmartDetectObjectType if t.audio_type is not None
]


class ProtectDeviceDetectionEventEntity(ProtectDevicePublicEventEntity):
    """A camera smart-detect category event entity (object or audio), public WS.

    Fires a momentary event for each detected type the entity surfaces. The
    ``event_types`` are derived from the uiprotect enum, so a new detection type
    is surfaced automatically without code changes (only a state label is added).
    The subscribed category comes from ``ufp_public_event_types``; the motion
    variant overrides the firing.
    """

    entity_description: ProtectDetectionEventEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the category's public detection events."""
        await super().async_added_to_hass()
        for event_type in self.entity_description.ufp_public_event_types:
            self.async_on_remove(
                self.data.async_subscribe_public_event(
                    self.device.id,
                    event_type,
                    self._async_detection_event,
                )
            )

    @callback
    def _async_detection_event(self, event: ProtectEvent) -> None:
        allowed = self.entity_description.event_types or ()
        # One fire per detected type so each stays independently automatable
        # (incl. types with no binary sensor); carries the co-detected set known
        # at fire time (types can still arrive on a later update).
        detected = [_event_type(t) for t in event.smart_detect_types]
        for event_type in detected:
            if event_type in allowed:
                self._fire_once(
                    event,
                    event_type,
                    {ATTR_EVENT_ID: event.id, ATTR_SMART_DETECT_TYPES: detected},
                )


class ProtectDeviceMotionEventEntity(ProtectDeviceDetectionEventEntity):
    """A camera motion-detection event entity (public events WS)."""

    @callback
    @override
    def _async_detection_event(self, event: ProtectEvent) -> None:
        self._fire_once(event, EventType.MOTION.value, {ATTR_EVENT_ID: event.id})


EVENT_DESCRIPTIONS: tuple[ProtectEventEntityDescription, ...] = (
    ProtectEventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        ufp_required_field="feature_flags.is_doorbell",
        event_types=[DoorbellEventType.RING],
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
    ProtectEventEntityDescription(
        key="package",
        translation_key="package",
        ufp_required_field="can_detect_package",
        ufp_obj_type=SmartDetectObjectType.PACKAGE,
        event_types=[EVENT_TYPE_PACKAGE_DETECTED],
        entity_class=ProtectDeviceSmartDetectEventEntity,
    ),
    ProtectDetectionEventEntityDescription(
        key="motion_detection",
        translation_key="motion_detection",
        device_class=EventDeviceClass.MOTION,
        event_types=[EventType.MOTION.value],
        ufp_public_event_types=(EventType.MOTION,),
        entity_class=ProtectDeviceMotionEventEntity,
    ),
    ProtectDetectionEventEntityDescription(
        key="smart_detection",
        translation_key="smart_detection",
        ufp_required_field="feature_flags.has_smart_detect",
        event_types=_SMART_OBJECT_EVENT_TYPES,
        ufp_public_event_types=_SMART_DETECT_EVENT_TYPES,
        entity_class=ProtectDeviceDetectionEventEntity,
    ),
    ProtectDetectionEventEntityDescription(
        key="sound_detection",
        translation_key="sound_detection",
        ufp_required_field="feature_flags.smart_detect_audio_types",
        event_types=_SMART_AUDIO_EVENT_TYPES,
        ufp_public_event_types=(EventType.SMART_AUDIO_DETECT,),
        entity_class=ProtectDeviceDetectionEventEntity,
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
        # AiPort inherits from Camera but should not create camera-specific entities
        if device.is_adopted and device.model is ModelType.CAMERA:
            async_add_entities(_async_event_entities(data, ufp_device=device))

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(_async_event_entities(data))
