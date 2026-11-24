"""Calendar platform for Axle Energy."""

from datetime import datetime
from typing import override

from aioaxlevpp import GridEvent

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import AxleConfigEntry, AxleCoordinator
from .entity import AxleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AxleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the grid event calendar."""
    async_add_entities([AxleCalendar(entry.runtime_data)])


class AxleCalendar(AxleEntity, CalendarEntity):
    """Represent the event currently announced by Axle."""

    _attr_translation_key = "events"

    def __init__(self, coordinator: AxleCoordinator) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or upcoming grid event."""
        if (event := self.coordinator.event) is None or event.end <= dt_util.utcnow():
            return None
        return _calendar_event(event)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the cached grid event if it overlaps the requested range."""
        if (
            (event := self.coordinator.event) is None
            or start_date == end_date
            or event.end < start_date
            or event.start >= end_date
        ):
            return []
        return [_calendar_event(event)]


def _calendar_event(event: GridEvent) -> CalendarEvent:
    """Convert a validated Axle event into a calendar event."""
    return CalendarEvent(
        start=event.start, end=event.end, summary=event.direction.capitalize()
    )
