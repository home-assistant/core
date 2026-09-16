"""Binary sensor platform for Axle Energy."""

from datetime import datetime
from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .coordinator import AxleConfigEntry, AxleCoordinator
from .entity import AxleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AxleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event activity sensor."""
    async_add_entities([AxleEventSensor(entry.runtime_data)])


class AxleEventSensor(AxleEntity, BinarySensorEntity):
    """Indicate whether the household's scheduled event is in progress."""

    _attr_translation_key = "event_in_progress"
    _unsub_refresh: CALLBACK_TYPE | None = None

    def __init__(self, coordinator: AxleCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_event_in_progress"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the current time is within the event."""
        if (event := self.coordinator.data) is None:
            return False
        return event.start <= dt_util.utcnow() < event.end

    @override
    async def async_added_to_hass(self) -> None:
        """Schedule the next event boundary."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_refresh)
        self._schedule_refresh()

    @callback
    def _cancel_refresh(self) -> None:
        """Cancel the scheduled boundary."""
        if self._unsub_refresh is not None:
            self._unsub_refresh()
            self._unsub_refresh = None

    @callback
    def _schedule_refresh(self) -> None:
        """Track the next boundary without an additional API request."""
        self._cancel_refresh()
        if not self.available or (event := self.coordinator.data) is None:
            return
        now = dt_util.utcnow()
        for boundary in (event.start, event.end):
            if boundary > now:
                self._unsub_refresh = async_track_point_in_utc_time(
                    self.hass, self._handle_refresh, boundary
                )
                return

    @callback
    def _handle_refresh(self, now: datetime) -> None:
        """Update the state at an event boundary."""
        self._unsub_refresh = None
        self._schedule_refresh()
        self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Replace the boundary timer when the schedule changes."""
        self._schedule_refresh()
        super()._handle_coordinator_update()
