"""Calendar platform for the Skylight integration."""

from datetime import date, datetime, timedelta
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SkylightConfigEntry
from .entity import SkylightEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    async_add_entities([SkylightCalendarEntity(entry.runtime_data, entry)])


def _as_datetime(value: date | datetime) -> datetime:
    """Normalise a CalendarEvent start/end (date or datetime) to a datetime."""
    if isinstance(value, datetime):
        return value
    return dt_util.start_of_local_day(value)


class SkylightCalendarEntity(SkylightEntity, CalendarEntity):
    """Representation of a Skylight frame calendar."""

    _attr_translation_key = "calendar"

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        upcoming = [
            event
            for event in self.coordinator.data.events
            if _as_datetime(event.end) > now
        ]
        upcoming.sort(key=lambda event: _as_datetime(event.start))
        return upcoming[0] if upcoming else None

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all events within a specific time frame."""
        return [
            event
            for event in self.coordinator.data.events
            if _as_datetime(event.start) < end_date + timedelta(days=1)
            and _as_datetime(event.end) > start_date
        ]
