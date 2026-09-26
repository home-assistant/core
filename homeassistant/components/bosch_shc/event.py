"""Platform for event integration."""

from typing import TYPE_CHECKING, Any, override

from boschshcpy import SHCMotionDetector, SHCMotionDetector2, SHCSmokeDetector

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 0

ATTR_LAST_TIME_TRIGGERED = "last_time_triggered"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC event platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[EventEntity] = [
        MotionDetectorEvent(
            hass=hass,
            device=motion_detector,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for motion_detector in session.device_helper.motion_detectors
    ]
    entities.extend(
        MotionDetectorEvent(
            hass=hass,
            device=motion_detector,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for motion_detector in session.device_helper.motion_detectors2
    )
    entities.extend(
        SmokeDetectorEvent(
            hass=hass,
            device=smoke_detector,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for smoke_detector in session.device_helper.smoke_detectors
    )

    async_add_entities(entities)


class MotionDetectorEvent(SHCEntity, EventEntity):
    """Representation of a SHC motion detector event."""

    _attr_name = None
    _attr_device_class = EventDeviceClass.MOTION
    _attr_event_types = ["motion"]
    _device: SHCMotionDetector | SHCMotionDetector2

    def __init__(
        self,
        hass: HomeAssistant,
        device: SHCMotionDetector | SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the motion detector event entity."""
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        # Dedup guard: LatestMotion replays the last timestamp on unrelated
        # long-poll updates for the same device (e.g. a battery-level change).
        # Seeded from the device's current value in async_added_to_hass so a
        # pre-existing timestamp isn't replayed as a new event on startup.
        self._last_fired_timestamp = ""

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to SHC events."""
        await super().async_added_to_hass()
        self._last_fired_timestamp = self._device.latestmotion or ""
        for service in self._device.device_services:
            if service.id == "LatestMotion":
                service.register_event(self._device.id, self._event_callback)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister the LatestMotion event callback."""
        await super().async_will_remove_from_hass()
        # register_event() has no public unsubscribe counterpart.
        for service in self._device.device_services:
            if service.id == "LatestMotion":
                service._event_callbacks.pop(self._device.id, None)  # noqa: SLF001

    def _event_callback(self) -> None:
        """Handle a LatestMotion update from the SHC polling thread."""
        timestamp = self._device.latestmotion or ""
        if timestamp == self._last_fired_timestamp:
            return
        self._last_fired_timestamp = timestamp
        self.hass.loop.call_soon_threadsafe(self._dispatch_event, timestamp)

    @callback
    def _dispatch_event(self, timestamp: str) -> None:
        """Trigger the event and write state on the event loop."""
        event_attributes: dict[str, Any] = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
            ATTR_LAST_TIME_TRIGGERED: timestamp,
        }
        self._trigger_event("motion", event_attributes)
        self.async_write_ha_state()


class SmokeDetectorEvent(SHCEntity, EventEntity):
    """Representation of a SHC smoke detector alarm event."""

    _attr_name = None
    _attr_translation_key = "smoke_detector_alarm"
    _attr_event_types = [
        "idle_off",
        "primary_alarm",
        "secondary_alarm",
        "intrusion_alarm",
        "intrusion_alarm_on_requested",
        "intrusion_alarm_off_requested",
    ]
    _device: SHCSmokeDetector

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to SHC events."""
        await super().async_added_to_hass()
        for service in self._device.device_services:
            if service.id == "Alarm":
                service.register_event(self._device.id, self._event_callback)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister the Alarm event callback."""
        await super().async_will_remove_from_hass()
        # register_event() has no public unsubscribe counterpart.
        for service in self._device.device_services:
            if service.id == "Alarm":
                service._event_callbacks.pop(self._device.id, None)  # noqa: SLF001

    def _event_callback(self) -> None:
        """Handle an Alarm update from the SHC polling thread."""
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_event, self._device.alarmstate.name.lower()
        )

    @callback
    def _dispatch_event(self, alarm_state: str) -> None:
        """Trigger the event and write state on the event loop."""
        event_attributes: dict[str, Any] = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_ID: self._device.id,
            ATTR_NAME: self._device.name,
        }
        self._trigger_event(alarm_state, event_attributes)
        self.async_write_ha_state()
