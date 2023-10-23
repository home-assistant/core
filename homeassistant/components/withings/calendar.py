"""Calendar platform for Withings."""
from __future__ import annotations

from datetime import datetime

from aiowithings import WithingsClient, WorkoutCategory

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, WithingsData
from .coordinator import WithingsActivityDataUpdateCoordinator
from .entity import WithingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    withings_data: WithingsData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            WithingsWorkoutCalendarEntity(
                withings_data.client, withings_data.activity_coordinator
            )
        ],
    )


def get_event_name(category: WorkoutCategory) -> str:
    """Return human-readable category."""
    name = category.name.lower().capitalize()
    return name.replace("_", " ")


class WithingsWorkoutCalendarEntity(CalendarEntity, WithingsEntity):
    """A calendar entity."""

    _attr_translation_key = "workout"

    coordinator: WithingsActivityDataUpdateCoordinator

    def __init__(
        self, client: WithingsClient, coordinator: WithingsActivityDataUpdateCoordinator
    ) -> None:
        """Create the Calendar entity."""
        super().__init__(coordinator, "workout")
        self.client = client

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        workouts = await self.client.get_workouts_in_period(
            start_date.date(), end_date.date()
        )
        event_list = []
        for workout in workouts:
            event = CalendarEvent(
                start=workout.start_date,
                end=workout.end_date,
                summary=get_event_name(workout.category),
            )

            event_list.append(event)

        return event_list
