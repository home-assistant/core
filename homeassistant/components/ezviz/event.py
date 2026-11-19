"""Support for EZVIZ motion events."""

from typing import override

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 0

EVENT_MOTION = "motion"

EVENT_TYPE = EventEntityDescription(
    key="motion",
    translation_key="motion",
    device_class=EventDeviceClass.MOTION,
    event_types=[EVENT_MOTION],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ event entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        EzvizMotionEvent(coordinator, camera) for camera in coordinator.data
    )


class EzvizMotionEvent(EzvizEntity, EventEntity):
    """Fires an event for each new alarm reported by an EZVIZ camera."""

    entity_description = EVENT_TYPE

    def __init__(self, coordinator: EzvizDataUpdateCoordinator, serial: str) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_{EVENT_TYPE.key}"
        # The alarm that is already there at startup is not a new event.
        self._last_alarm_time = self.data.get("last_alarm_time")

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Fire the event when the camera reports a new alarm."""
        # Write the availability first, so that an alarm that arrives with the
        # first refresh after an outage is a separate state change and is not
        # dropped by triggers that ignore changes from unavailable.
        super()._handle_coordinator_update()
        # Keep an alarm reported while the camera is offline until it is back,
        # otherwise the event is written while unavailable and gets lost.
        if not self.available:
            return
        last_alarm_time = self.data.get("last_alarm_time")
        if last_alarm_time and last_alarm_time != self._last_alarm_time:
            self._last_alarm_time = last_alarm_time
            self._trigger_event(
                EVENT_MOTION,
                {
                    "alarm_type_code": self.data.get("last_alarm_type_code"),
                    "alarm_type_name": self.data.get("last_alarm_type_name"),
                },
            )
            self.async_write_ha_state()
