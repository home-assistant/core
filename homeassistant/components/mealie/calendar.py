"""Calendar platform for Mealie."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiomealie import Mealplan, MealplanEntryType

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


def get_event_from_mealplan(mealplan: Mealplan) -> CalendarEvent:
    """Create a CalendarEvent from a Mealplan."""
    mealplan_date = mealplan.mealplan_date
    start_of_day = datetime(mealplan_date.year, mealplan_date.month, mealplan_date.day)
    end_of_day = start_of_day + timedelta(days=1)
    return CalendarEvent(
        start=start_of_day,
        end=end_of_day,
        summary=mealplan.recipe.name,
    )


class MealieMealplanCalendarEntity(MealieEntity, CalendarEntity):
    """A calendar entity."""

    def __init__(
        self, coordinator: MealieCoordinator, entry_type: MealplanEntryType
    ) -> None:
        """Create the Calendar entity."""
        super().__init__(coordinator)
        self._entry_type = entry_type
        self._attr_translation_key = entry_type.name.lower()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        mealplans = self.coordinator.data[self._entry_type]
        if not mealplans:
            return None
        return get_event_from_mealplan(mealplans[0])

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        mealplans = (
            await self.coordinator.client.get_mealplans(
                start_date.date(), end_date.date()
            )
        ).items
        return [get_event_from_mealplan(mealplan) for mealplan in mealplans]
