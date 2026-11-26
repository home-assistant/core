"""Support for EZVIZ motion events."""

from dataclasses import dataclass
from typing import override

from pyezvizapi.devices.intercom_events import intercom_event_type

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
    EventExtraStoredData,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 0

EVENT_MOTION = "motion"
ATTR_ALARM_TIME = "alarm_time"

EVENT_TYPE = EventEntityDescription(
    key="motion",
    translation_key="motion",
    device_class=EventDeviceClass.MOTION,
    event_types=[EVENT_MOTION],
)


@dataclass
class EzvizEventExtraStoredData(EventExtraStoredData):
    """Event data plus the last alarm handled, fired or not."""

    last_alarm_time: str | None = None


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

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last handled alarm when the camera does not report one yet."""
        await super().async_added_to_hass()
        if self._last_alarm_time is None and (
            extra := await self.async_get_last_extra_data()
        ):
            self._last_alarm_time = extra.as_dict().get("last_alarm_time")

    @property
    @override
    def extra_restore_state_data(self) -> EzvizEventExtraStoredData:
        """Store the last handled alarm, also when it was not fired as an event.

        The alarm already present at startup is handled without firing, so it
        is not in the event attributes.
        """
        event_data = super().extra_restore_state_data
        return EzvizEventExtraStoredData(
            event_data.last_event_type,
            event_data.last_event_attributes,
            self._last_alarm_time,
        )

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
            # Doorbell rings and unlocks are reported as alarms too: they are
            # handled, so they do not fire later, but they are not motion.
            if intercom_event_type(self.data.get("last_alarm_type_code")):
                return
            self._trigger_event(
                EVENT_MOTION,
                {
                    ATTR_ALARM_TIME: last_alarm_time,
                    "alarm_type_code": self.data.get("last_alarm_type_code"),
                    "alarm_type_name": self.data.get("last_alarm_type_name"),
                },
            )
            self.async_write_ha_state()
