"""Support for Sonarr calendar items."""

from datetime import datetime, timedelta
from typing import override

from aiopyarr import SonarrCalendar

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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


def _get_calendar_event(episode: SonarrCalendar) -> CalendarEvent | None:
    """Return a CalendarEvent from a Sonarr calendar item."""
    if episode.airDateUtc is None:
        return None
    start = dt_util.as_utc(episode.airDateUtc)
    summary = (
        f"{episode.series.title} - "
        f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}"
    )
    if episode.title:
        summary = f"{summary} - {episode.title}"
    return CalendarEvent(
        summary=summary,
        start=start,
        end=start + timedelta(minutes=episode.series.runtime),
        description=getattr(episode, "overview", None) or None,
    )


class SonarrCalendarEntity(SonarrEntity[list[SonarrCalendar]], CalendarEntity):
    """A Sonarr calendar entity."""

    coordinator: CalendarDataUpdateCoordinator

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        events = sorted(
            (
                event
                for episode in self.coordinator.data
                if (event := _get_calendar_event(episode)) is not None
            ),
            key=lambda event: event.start,
        )
        return next((event for event in events if event.end > now), None)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        episodes = await self.coordinator.api_client.async_get_calendar(
            start_date=start_date, end_date=end_date, include_series=True
        )
        return [
            event
            for episode in episodes
            if (event := _get_calendar_event(episode)) is not None
        ]
