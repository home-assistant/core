"""Calendar platform for Junker."""

import datetime as dt
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import JunkerConfigEntry, JunkerDataUpdateCoordinator
from .entity import JunkerEntity
from .junker_api import Collection

PARALLEL_UPDATES = 0


def _event_from_collection(collection: Collection) -> CalendarEvent:
    """Create a calendar event from a collection."""
    return CalendarEvent(
        summary=collection.waste_type,
        start=collection.date,
        end=collection.date + dt.timedelta(days=1),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JunkerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Junker calendar."""
    async_add_entities([JunkerCalendar(entry.runtime_data, entry)])


class JunkerCalendar(JunkerEntity, CalendarEntity):
    """Calendar of waste collections supplied by Junker."""

    _attr_translation_key = "calendar"

    def __init__(
        self,
        coordinator: JunkerDataUpdateCoordinator,
        entry: JunkerConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = self._identifier

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next scheduled collection."""
        today = dt_util.now().date()
        return next(
            (
                _event_from_collection(collection)
                for collection in self.collections
                if collection.date > today
            ),
            None,
        )

    @override
    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events in the requested range."""
        return [
            _event_from_collection(collection)
            for collection in self.collections
            if start_date.date() <= collection.date <= end_date.date()
        ]
