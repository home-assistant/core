"""Support for Sonarr calendar items."""

from datetime import datetime

from aiopyarr import SonarrCalendar

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CalendarDataUpdateCoordinator, SonarrConfigEntry
from .entity import SonarrEntity

CALENDAR_TYPE = CalendarEntityDescription(
    key="calendar",
    name=None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonarrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sonarr calendar entity."""
    coordinator = entry.runtime_data.upcoming
    async_add_entities([SonarrCalendarEntity(coordinator, CALENDAR_TYPE)])


class SonarrCalendarEntity(SonarrEntity[list[SonarrCalendar]], CalendarEntity):
    """A Sonarr calendar entity."""

    coordinator: CalendarDataUpdateCoordinator

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self.coordinator.event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self.coordinator.async_get_events(start_date, end_date)
