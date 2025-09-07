"""Calendar platform for Mealie."""

from __future__ import annotations

from datetime import datetime, time

from aiomealie import Mealplan, MealplanEntryType

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import LOGGER, MEAL_TIME
from .coordinator import MealieConfigEntry, MealieMealplanCoordinator
from .entity import MealieEntity

PARALLEL_UPDATES = 0


def _get_meal_time(
    entry: MealieConfigEntry,
    entry_type: MealplanEntryType,
) -> time:
    meal = MEAL_TIME[entry_type]
    _time = cv.time(entry.data.get(meal.text, meal.default))
    return time(
        hour=_time.hour,
        minute=_time.minute,
        second=_time.second,
        tzinfo=dt_util.DEFAULT_TIME_ZONE,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator = entry.runtime_data.mealplan_coordinator

    meal_times = {
        entry_type.name: _get_meal_time(entry, entry_type)
        for entry_type in MealplanEntryType
    }

    async_add_entities(
        MealieMealplanCalendarEntity(
            coordinator, entry_type, meal_times[entry_type.name]
        )
        for entry_type in MealplanEntryType
    )


def _get_event_from_mealplan(
    mealplan: Mealplan, override_meal_time: time
) -> CalendarEvent:
    """Create a CalendarEvent from a Mealplan."""
    description: str | None = mealplan.description
    name = mealplan.title or "No recipe"
    if mealplan.recipe:
        name = mealplan.recipe.name
        description = mealplan.recipe.description
    meal_time = datetime.combine(mealplan.mealplan_date, override_meal_time)
    meal_time_tz = meal_time  # time.tzname.localize(meal_time)
    LOGGER.info(
        f"Cal event {name} with description {description} and meal time {meal_time_tz}"
    )
    return CalendarEvent(
        start=meal_time,
        end=meal_time,
        summary=name,
        description=description,
    )


class MealieMealplanCalendarEntity(MealieEntity, CalendarEntity):
    """A calendar entity."""

    def __init__(
        self,
        coordinator: MealieMealplanCoordinator,
        entry_type: MealplanEntryType,
        override_meal_time: time,
    ) -> None:
        """Create the Calendar entity."""
        super().__init__(coordinator, entry_type.name.lower())
        self._entry_type = entry_type
        self._attr_translation_key = entry_type.name.lower()
        self.override_meal_time = override_meal_time

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        mealplans = self.coordinator.data[self._entry_type]
        if not mealplans:
            return None
        sorted_mealplans = sorted(mealplans, key=lambda x: x.mealplan_date)
        return _get_event_from_mealplan(sorted_mealplans[0], self.override_meal_time)

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
            _get_event_from_mealplan(mealplan, self.override_meal_time)
            for mealplan in mealplans
            if mealplan.entry_type is self._entry_type
        ]
