"""Calendar platform for the Skylight integration."""

from datetime import datetime
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SkylightConfigEntry, _as_datetime
from .entity import SkylightEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    async_add_entities([SkylightCalendarEntity(entry.runtime_data, entry)])


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
        return await self.coordinator.async_events_between(start_date, end_date)
