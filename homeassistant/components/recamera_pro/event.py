"""YOLO detection event entity for reCamera Pro."""

import logging

from recamera_protocol import ResultObservation

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntryHider

from .const import DOMAIN, SOURCE_UNAVAILABLE
from .coordinator import RecameraCoordinator
from .entity import RecameraEntity
from .source_state import DetectionState, EventRecord

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
_PENDING_EVENT_LIMIT = 64


def _event_attributes(
    observation: ResultObservation,
) -> dict[str, object]:
    """Return bounded YOLO event attributes."""
    return {
        "source_id": observation.source_id,
        "family": ("audio" if observation.source_id == "acousticslab" else "visual"),
        "task_type": observation.task_type,
        "class_id": observation.class_id,
        "class_name": observation.class_name,
        "class_key": observation.class_key,
        "confidence": observation.confidence,
        "occurred_at": observation.timestamp.isoformat(),
        "received_at": observation.received_at.isoformat(),
        "clock_valid": observation.clock_valid,
        "device_wall_ms": observation.device_wall_ms,
        "track_id": observation.track_id,
        "box": observation.box,
        "event_id": observation.event_id,
        "event_key": observation.class_key,
        "raw_json": observation.raw_json,
    }


class RecameraDetectionEvent(RecameraEntity, EventEntity):
    """Publish accepted entries for one detection source."""

    _attr_event_types: list[str] = []
    _source_id: str
    _unique_suffix: str

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize the source event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{self._unique_suffix}"
        self._attr_event_types = []
        self._event_ready = False
        self._event_active = True
        self._pending_records: list[EventRecord] = []
        self._last_serial = self._state.event_serial
        self._queued_serial = self._last_serial
        self._last_available: bool | None = None
        self._sync_event_types()

    @property
    def _state(self) -> DetectionState:
        """Return the source state."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        """Keep event history available while the integration is loaded."""
        return super().available

    @callback
    def _sync_event_types(self) -> None:
        """Synchronize selectable YOLO class names."""
        event_types = {record.observation.class_name for record in self._state.events}
        event_types.update(
            item.class_name
            for item in self.coordinator.data.class_catalog.values()
            if item.source_id == self._source_id
        )
        event_types.discard("")
        self._attr_event_types[:] = sorted(event_types)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Queue new YOLO events without writing before registration."""
        if not self._event_active:
            return
        self._sync_event_types()
        for record in self._state.events:
            if record.serial <= self._queued_serial:
                continue
            self._pending_records.append(record)
            self._queued_serial = record.serial
            if len(self._pending_records) > _PENDING_EVENT_LIMIT:
                dropped = self._pending_records.pop(0)
                _LOGGER.warning(
                    "Dropping oldest pending YOLO event %s",
                    dropped.serial,
                )
        had_new_events = bool(self._pending_records)
        self._flush_pending_events()
        available = self.available
        if not had_new_events and available != self._last_available:
            self.async_write_ha_state()
        self._last_available = available

    @callback
    def _flush_pending_events(self) -> None:
        """Publish pending YOLO events in order."""
        if not self._event_ready or not self._event_active:
            return
        while self._pending_records:
            record = self._pending_records[0]
            observation = record.observation
            if observation.class_name not in self._attr_event_types:
                self._attr_event_types.append(observation.class_name)
                self._attr_event_types.sort()
            context = (
                record.context if isinstance(record.context, Context) else Context()
            )
            self.async_set_context(context)
            self._trigger_event(
                observation.class_name,
                _event_attributes(observation),
            )
            self._last_serial = record.serial
            self._pending_records.pop(0)
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Flush events queued during entity registration."""
        await super().async_added_to_hass()
        self._event_ready = True
        self._last_available = self.available
        self._flush_pending_events()

    async def async_will_remove_from_hass(self) -> None:
        """Ignore coordinator updates during unload."""
        self._event_active = False
        self._event_ready = False
        self._pending_records.clear()
        await super().async_will_remove_from_hass()


class RecameraYoloEvent(RecameraDetectionEvent):
    """Publish accepted builtin YOLO class entries."""

    _attr_translation_key = "yolo_event"
    _source_id = "builtin"
    _unique_suffix = "visual_event"

    @property
    def _state(self) -> DetectionState:
        """Return builtin YOLO state."""
        return self.coordinator.data.visual


class RecameraSoundEvent(RecameraDetectionEvent):
    """Publish accepted acoustic classifications."""

    _attr_translation_key = "audio_event"
    _source_id = "acousticslab"
    _unique_suffix = "audio_event"

    @property
    def _state(self) -> DetectionState:
        """Return acoustic state."""
        return self.coordinator.data.audio


class RecameraMotionEvent(RecameraEntity, EventEntity):
    """Publish motion start and stop transitions."""

    _attr_translation_key = "motion_event"
    _attr_event_types = ["motion_started", "motion_stopped"]
    _attr_icon = "mdi:motion-play-outline"
    _PENDING_EVENT_LIMIT = 64

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize the motion event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_motion_detected_event"
        self._event_ready = False
        self._event_active = True
        motion = coordinator.data.motion
        self._last_motion = motion.motion if motion.running else None
        self._pending_events: list[tuple[str, dict[str, object]]] = []
        self._last_available = self.available

    @property
    def available(self) -> bool:
        """Return whether motion lifecycle data is confirmed."""
        motion = self.coordinator.data.motion
        return super().available and motion.app_health != SOURCE_UNAVAILABLE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Queue motion transitions without writing before registration."""
        if not self._event_active:
            return
        motion = self.coordinator.data.motion
        if motion.app_health == SOURCE_UNAVAILABLE or not motion.running:
            self._last_motion = None
            self._flush_pending_events()
            self._write_availability_change()
            return
        current = motion.motion if motion.running else None
        if current is None:
            self._flush_pending_events()
            self._write_availability_change()
            return
        if self._last_motion is None:
            event_type = "motion_started" if current else None
        elif self._last_motion != current:
            event_type = "motion_started" if current else "motion_stopped"
        else:
            event_type = None
        self._last_motion = current
        if event_type is not None:
            self._queue_event(event_type)
        self._flush_pending_events()
        self._write_availability_change()

    @callback
    def _queue_event(self, event_type: str) -> None:
        """Queue one bounded motion event."""
        self._pending_events.append((event_type, self._event_attributes()))
        if len(self._pending_events) > self._PENDING_EVENT_LIMIT:
            self._pending_events.pop(0)
            _LOGGER.warning(
                "Dropping oldest pending motion event for %s",
                self.entity_id,
            )

    def _event_attributes(self) -> dict[str, object]:
        """Return the latest motion metrics as event attributes."""
        motion = self.coordinator.data.motion
        return {
            "source_id": "motion-detect",
            "app_running": motion.running,
            "score": motion.score,
            "changed_ratio": motion.changed_ratio,
            "changed_pixels": motion.changed_pixels,
            "detected_at": (
                motion.last_seen.isoformat() if motion.last_seen is not None else None
            ),
            "event_id": motion.event_id,
            "sequence": motion.sequence,
            "app_health": motion.app_health,
            "error": motion.error,
        }

    @callback
    def _write_availability_change(self) -> None:
        """Publish availability changes even without a new transition."""
        available = self.available
        if available != self._last_available:
            self.async_write_ha_state()
        self._last_available = available

    @callback
    def _flush_pending_events(self) -> None:
        """Publish queued motion transitions in order."""
        if not self._event_ready or not self._event_active:
            return
        while self._pending_events:
            event_type, attributes = self._pending_events.pop(0)
            self._trigger_event(event_type, attributes)
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Flush transitions queued during entity registration."""
        await super().async_added_to_hass()
        self._event_ready = True
        self._flush_pending_events()

    async def async_will_remove_from_hass(self) -> None:
        """Ignore coordinator updates during unload."""
        self._event_active = False
        self._event_ready = False
        self._pending_events.clear()
        await super().async_will_remove_from_hass()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YOLO and sound event entities."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    entities: list[RecameraDetectionEvent | RecameraMotionEvent] = [
        RecameraYoloEvent(coordinator),
        RecameraSoundEvent(coordinator),
    ]
    motion_added = coordinator.data.motion.installed
    if motion_added:
        entities.append(RecameraMotionEvent(coordinator))
    async_add_entities(entities)

    @callback
    def _add_motion_event() -> None:
        nonlocal motion_added
        if motion_added or not coordinator.data.motion.installed:
            return
        motion_added = True
        async_add_entities([RecameraMotionEvent(coordinator)])

    config_entry.async_on_unload(coordinator.async_add_listener(_add_motion_event))
    _hide_removed_event_entities(hass, coordinator)


def _hide_removed_event_entities(
    hass: HomeAssistant, coordinator: RecameraCoordinator
) -> None:
    """Hide obsolete App events and keep YOLO/sound registrations."""
    registry = er.async_get(hass)
    device_id = coordinator.device_id
    entry_id = coordinator.config_entry.entry_id
    kept_unique_ids = {
        f"{device_id}_visual_event",
        f"{device_id}_audio_event",
        f"{device_id}_motion_detected_event",
    }
    for unique_id in kept_unique_ids:
        kept_entity_id = registry.async_get_entity_id("event", DOMAIN, unique_id)
        if kept_entity_id is not None:
            kept = registry.async_get(kept_entity_id)
            if kept is not None and kept.hidden_by == RegistryEntryHider.INTEGRATION:
                registry.async_update_entity(kept_entity_id, hidden_by=None)
    for entry in list(registry.entities.values()):
        if (
            entry.platform != DOMAIN
            or entry.config_entry_id != entry_id
            or not str(entry.entity_id).startswith("event.")
            or entry.unique_id in kept_unique_ids
        ):
            continue
        if "_app_event_" in str(entry.unique_id) or entry.unique_id.endswith(
            "_ai_event"
        ):
            if entry.hidden_by != RegistryEntryHider.USER:
                registry.async_update_entity(
                    entry.entity_id,
                    hidden_by=RegistryEntryHider.INTEGRATION,
                )
            continue
        if entry.hidden_by == RegistryEntryHider.USER:
            continue
        if entry.hidden_by != RegistryEntryHider.INTEGRATION:
            registry.async_update_entity(
                entry.entity_id,
                hidden_by=RegistryEntryHider.INTEGRATION,
            )
