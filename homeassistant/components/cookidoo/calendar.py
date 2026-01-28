"""Calendar platform for the Cookidoo integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from cookidoo_api import CookidooAuthException, CookidooException
from cookidoo_api.types import CookidooCalendarDayRecipe

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .entity import CookidooBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CookidooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator = config_entry.runtime_data

    async_add_entities([CookidooCalendarEntity(coordinator)])


def recipe_to_event(day_date: date, recipe: CookidooCalendarDayRecipe) -> CalendarEvent:
    """Convert a Cookidoo recipe to a CalendarEvent."""
    return CalendarEvent(
        start=day_date,
        end=day_date + timedelta(days=1),  # All-day event
        summary=recipe.name,
        description=f"Total Time: {recipe.total_time}",
    )


class CookidooCalendarEntity(CookidooBaseEntity, CalendarEntity):
    """A calendar entity."""

    _attr_translation_key = "meal_plan"

    def __init__(self, coordinator: CookidooDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry.unique_id
        self._attr_unique_id = coordinator.config_entry.unique_id

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if not self.coordinator.data.week_plan:
            return None

        today = date.today()
        for day_data in self.coordinator.data.week_plan:
            day_date = date.fromisoformat(day_data.id)
            if day_date >= today and day_data.recipes:
                recipe = day_data.recipes[0]
                return recipe_to_event(day_date, recipe)
        return None

    async def _fetch_week_plan(self, week_day: date) -> list:
        """Fetch a single Cookidoo week plan, retrying once on auth failure."""
        try:
            return await self.coordinator.cookidoo.get_recipes_in_calendar_week(
                week_day
            )
        except CookidooAuthException:
            await self.coordinator.cookidoo.refresh_token()
            return await self.coordinator.cookidoo.get_recipes_in_calendar_week(
                week_day
            )
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="calendar_fetch_failed",
            ) from e

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events: list[CalendarEvent] = []
        current_day = start_date.date()
        while current_day <= end_date.date():
            week_plan = await self._fetch_week_plan(current_day)
            for day_data in week_plan:
                day_date = date.fromisoformat(day_data.id)
                if start_date.date() <= day_date <= end_date.date():
                    events.extend(
                        recipe_to_event(day_date, recipe) for recipe in day_data.recipes
                    )
            current_day += timedelta(days=7)  # Move to the next week
        return events
