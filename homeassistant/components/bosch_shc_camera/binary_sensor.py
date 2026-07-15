"""Bosch Smart Home Camera — Binary Sensor Platform.

Creates binary sensor entities per camera:
  • {Name} Motion           — ON when a MOVEMENT event was detected within the configurable active window (default 90 s)
  • {Name} Audio Alarm      — ON when an AUDIO_ALARM event was detected within the configurable active window (default 90 s)
  • {Name} Person Detected  — ON when a PERSON event was detected within the configurable active window (default 90 s)

All sensors are disabled by default (entity_registry_enabled_default = False).
Enable them in Settings → Entities if you want to trigger automations from motion/audio/person events.

Event data is read from coordinator.data[cam_id]["events"] (the most recent event list).
The sensors go ON when the most-recent event matches the type AND its timestamp is within
the configurable active window (default 90 s); otherwise they are OFF.

Device class:
  motion binary sensor  → BinarySensorDeviceClass.MOTION
  audio  binary sensor  → BinarySensorDeviceClass.SOUND
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import time as _time
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, BoschCameraConfigEntry, BoschCameraCoordinator
from .const import (
    DEFAULT_MOTION_ACTIVE_WINDOW,
    MOTION_ACTIVE_WINDOW_MAX,
    MOTION_ACTIVE_WINDOW_MIN,
)
from .models import get_display_name
from .time_utils import parse_bosch_timestamp

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = (
    0  # coordinator handles all updates; no per-entity parallelism needed
)

# Module-level fallback — keeps tests and external code that reference
# EVENT_ACTIVE_WINDOW directly working unchanged.  Production code reads
# the per-entry option via `_motion_active_window` (see below).
EVENT_ACTIVE_WINDOW = DEFAULT_MOTION_ACTIVE_WINDOW


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities for each camera."""
    coordinator: BoschCameraCoordinator = config_entry.runtime_data
    entities: list[_BoschBinarySensorBase] = []
    for cam_id in coordinator.data:
        cam_info = coordinator.data[cam_id].get("info", {})
        has_sound = cam_info.get("featureSupport", {}).get("sound", False)
        entities.append(BoschMotionBinarySensor(coordinator, cam_id, config_entry))
        entities.append(
            BoschPersonDetectedBinarySensor(coordinator, cam_id, config_entry)
        )
        entities.append(
            BoschLanReachableBinarySensor(coordinator, cam_id, config_entry)
        )
        if has_sound:
            entities.append(
                BoschAudioAlarmBinarySensor(coordinator, cam_id, config_entry)
            )
    async_add_entities(entities, update_before_add=False)


# ─────────────────────────────────────────────────────────────────────────────
class _BoschBinarySensorBase(
    CoordinatorEntity[BoschCameraCoordinator], BinarySensorEntity
):
    """Shared base for Bosch camera binary sensors."""

    # Disabled by default — enable explicitly in entity registry if desired
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry

        info = coordinator.data.get(cam_id, {}).get("info", {})
        self._cam_title = info.get("title", cam_id)
        self._model = info.get("hardwareVersion", "CAMERA")
        self._model_name = get_display_name(self._model)
        self._fw = info.get("firmwareVersion", "")
        self._mac = info.get("macAddress", "")

    @property
    def _cam_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._cam_id, {})  # type: ignore[no-any-return]

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": self._model_name,
            "sw_version": self._fw,
            "connections": {("mac", self._mac)} if self._mac else set(),
        }

    def _get_latest_event_of_type(self, event_type: str) -> dict[str, Any] | None:
        """Return the most recent event matching event_type, or None."""
        events = self._cam_data.get("events", [])
        for ev in events:
            if ev.get("eventType", "") == event_type:
                return ev  # type: ignore[no-any-return]
        return None

    def _get_latest_person_event(self) -> dict[str, Any] | None:
        """Return the most recent event that represents a detected person.

        Gen2 cameras (Outdoor II / Indoor II, DualRadar) report a human as
        ``eventType="MOVEMENT"`` with ``eventTags=["PERSON"]`` rather than a bare
        ``PERSON`` type. The coordinator only upgrades a *local* variable to
        PERSON when firing the HA bus event — the raw event dict kept in
        ``coordinator.data[...]["events"]`` is never rewritten, so matching on
        ``eventType=="PERSON"`` alone left the Person sensor stuck OFF on Gen2
        (issue #36). Accept either the explicit PERSON type or a MOVEMENT event
        tagged PERSON, whichever is newer in the (newest-first) event list.
        """
        events = self._cam_data.get("events", [])
        for ev in events:
            event_type = ev.get("eventType", "")
            if event_type == "PERSON":
                return ev  # type: ignore[no-any-return]
            if event_type == "MOVEMENT" and "PERSON" in (ev.get("eventTags") or []):
                return ev  # type: ignore[no-any-return]
        return None

    @property
    def _motion_active_window(self) -> int:
        """Return the configured active-window duration in seconds.

        Reads `motion_active_window` from the config-entry options, falling
        back to DEFAULT_MOTION_ACTIVE_WINDOW (90 s) when the key is absent
        (legacy entries without the option).  The value is clamped to the
        valid range [MOTION_ACTIVE_WINDOW_MIN, MOTION_ACTIVE_WINDOW_MAX] so
        persisted out-of-range values (e.g. from a corrupted config) never
        cause surprising behaviour.
        """
        raw: Any = self._entry.options.get(
            "motion_active_window", DEFAULT_MOTION_ACTIVE_WINDOW
        )
        try:
            value: int = int(raw)
        except TypeError, ValueError:
            value = DEFAULT_MOTION_ACTIVE_WINDOW
        return max(MOTION_ACTIVE_WINDOW_MIN, min(MOTION_ACTIVE_WINDOW_MAX, value))

    def _event_within_window(self, event: dict[str, Any]) -> bool:
        """Return True if the event timestamp is within the active window seconds of now.

        Bosch /v11/events timestamps carry an explicit timezone designator —
        currently an offset, e.g. ``"2026-06-18T06:06:30.499+02:00[Europe/Berlin]"``,
        historically a ``Z`` suffix. The instant MUST be derived by honoring
        that designator (`parse_bosch_timestamp`), never by truncating it away:
        ``ts_str[:19]`` + ``replace(tzinfo=UTC)`` re-labelled the local
        wall-clock reading as UTC, so a fresh event appeared ~2h in the future
        (negative age → window stuck on) in CEST. Parsing the offset restores
        the true instant. (Originally reported via simon42 forum (geotie) as
        'Motion-Sensor wird oft nicht ausgelöst'; see issue #34.)

        The window duration is taken from `_motion_active_window` which reads
        the `motion_active_window` config-entry option (default 90 s, range
        10-300 s, configurable via Settings → Integrations → Configure).
        """
        dt_utc = parse_bosch_timestamp(event.get("timestamp"))
        if dt_utc is None:
            return False
        age = datetime.now(tz=UTC) - dt_utc
        return age <= timedelta(seconds=self._motion_active_window)


# ─────────────────────────────────────────────────────────────────────────────
class BoschMotionBinarySensor(_BoschBinarySensorBase):
    """Binary sensor: ON when a MOVEMENT event occurred within the configurable active window (default 90 s)."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_motion_binary"
        self._attr_translation_key = "motion"

    @property
    @override
    def is_on(self) -> bool:
        event = self._get_latest_event_of_type("MOVEMENT")
        if event is None:
            return False
        return self._event_within_window(event)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        event = self._get_latest_event_of_type("MOVEMENT")
        if not event:
            return {}
        return {
            "event_id": event.get("id", ""),
            "timestamp": event.get("timestamp", ""),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschAudioAlarmBinarySensor(_BoschBinarySensorBase):
    """Binary sensor: ON when an AUDIO_ALARM event occurred within the configurable active window (default 90 s)."""

    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_audio_alarm_binary"
        self._attr_translation_key = "audio_alarm_binary"

    @property
    @override
    def is_on(self) -> bool:
        event = self._get_latest_event_of_type("AUDIO_ALARM")
        if event is None:
            return False
        return self._event_within_window(event)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        event = self._get_latest_event_of_type("AUDIO_ALARM")
        if not event:
            return {}
        return {
            "event_id": event.get("id", ""),
            "timestamp": event.get("timestamp", ""),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschPersonDetectedBinarySensor(_BoschBinarySensorBase):
    """Binary sensor: ON when a PERSON event occurred within the configurable active window (default 90 s)."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_cam_{cam_id}_person_detected"
        self._attr_translation_key = "person_detected"

    @property
    @override
    def is_on(self) -> bool:
        event = self._get_latest_person_event()
        if event is None:
            return False
        return self._event_within_window(event)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        event = self._get_latest_person_event()
        if not event:
            return {}
        return {
            "event_id": event.get("id", ""),
            "timestamp": event.get("timestamp", ""),
        }


# ─────────────────────────────────────────────────────────────────────────────
class BoschLanReachableBinarySensor(_BoschBinarySensorBase):
    """Reports whether the camera answers a TCP connect on port 443.

    Always available — useful precisely when the Bosch cloud is unreachable.
    Honors the post-write grace period so a transient blip right after a
    privacy/light toggle does not flip the state to off (the camera briefly
    tears down its HTTPS endpoint while Digest creds rotate).
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "lan_reachable"
    _attr_entity_registry_enabled_default = True
    # Both freshness fields are monotonic-derived → they change on every
    # coordinator tick while the on/off state stays put. Recording them spawns
    # a new `state_attributes` row each tick and bloats the DB (HA#39). Keep
    # them visible live, but never historize them.
    _unrecorded_attributes = frozenset(
        {"last_check_seconds_ago", "write_grace_seconds_left"}
    )

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_lan_reachable"
        # Use HA's auto-naming via translation_key + device_info — no `name`
        # override here, otherwise the device-name prefix gets duplicated
        # into the slug, producing entity_ids like
        # `binary_sensor.bosch_<title>_bosch_<title>_lan_reachable`.

    @property
    @override
    def available(self) -> bool:
        return True

    @property
    @override
    def is_on(self) -> bool | None:
        is_lan_reachable = getattr(self.coordinator, "is_lan_reachable", None)
        if is_lan_reachable is None:
            return None
        result = is_lan_reachable(self._cam_id)
        return None if result is None else bool(result)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self.coordinator.lan_tcp_reachable.get(self._cam_id)
        attrs: dict[str, Any] = {"camera_id": self._cam_id}
        if entry is not None:
            _reachable, ts = entry
            attrs["last_check_seconds_ago"] = round(_time.monotonic() - ts)
        last_write = (
            self.coordinator.local_write_at.get(self._cam_id, float("-inf"))
            if hasattr(self.coordinator, "local_write_at")
            else float("-inf")
        )
        if last_write != float("-inf"):
            grace_left = self.coordinator.LOCAL_WRITE_GRACE_S - (
                _time.monotonic() - last_write
            )
            if grace_left > 0:
                attrs["write_grace_seconds_left"] = round(grace_left)
        return attrs
