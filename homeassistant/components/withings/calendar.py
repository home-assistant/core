"""Calendar platform for Withings."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from aiowithings import WithingsClient, WorkoutCategory

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, WithingsConfigEntry
from .coordinator import WithingsWorkoutDataUpdateCoordinator
from .entity import WithingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WithingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    ent_reg = er.async_get(hass)
    withings_data = entry.runtime_data

    workout_coordinator = withings_data.workout_coordinator

    calendar_setup_before = ent_reg.async_get_entity_id(
        Platform.CALENDAR,
        DOMAIN,
        f"withings_{entry.unique_id}_workout",
    )

    if workout_coordinator.data is not None or calendar_setup_before:
        async_add_entities(
            [WithingsWorkoutCalendarEntity(withings_data.client, workout_coordinator)],
        )
    else:
        remove_calendar_listener: Callable[[], None]

        def _async_add_calendar_entity() -> None:
            """Add calendar entity."""
            if workout_coordinator.data is not None:
                async_add_entities(
                    [
                        WithingsWorkoutCalendarEntity(
                            withings_data.client, workout_coordinator
                        )
                    ],
                )
                remove_calendar_listener()

        remove_calendar_listener = workout_coordinator.async_add_listener(
            _async_add_calendar_entity
        )


def get_event_name(category: WorkoutCategory) -> str:
    """Return human-readable category."""
    name = category.name.lower().capitalize()
    return name.replace("_", " ")


class WithingsWorkoutCalendarEntity(
    WithingsEntity[WithingsWorkoutDataUpdateCoordinator], CalendarEntity
):
    """A calendar entity."""

    _attr_translation_key = "workout"

    def __init__(
        self, client: WithingsClient, coordinator: WithingsWorkoutDataUpdateCoordinator
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
