"""Calendar platform for Mealie."""

from __future__ import annotations

from datetime import datetime

from aiomealie import MealplanEntryType

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MealieConfigEntry, MealieCoordinator
from .entity import MealieEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator = entry.runtime_data

    async_add_entities(
        MealieMealplanCalendarEntity(coordinator, entry_type)
        for entry_type in MealplanEntryType
    )


class MealieMealplanCalendarEntity(MealieEntity, CalendarEntity):
    """A calendar entity."""

    def __init__(
        self, coordinator: MealieCoordinator, entry_type: MealplanEntryType
    ) -> None:
        """Create the Calendar entity."""
        super().__init__(coordinator)
        self._attr_translation_key = entry_type.name.lower()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        mealplans = (
            await self.coordinator.client.get_mealplans(
                start_date.date(), end_date.date()
            )
        ).items
        return [
            CalendarEvent(
                start=mealplan.mealplan_date,
                end=mealplan.mealplan_date,
                summary=mealplan.recipe.name,
            )
            for mealplan in mealplans
        ]
