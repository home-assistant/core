"""Support for Sonarr calendar."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_utc

from .const import DOMAIN
from .coordinator import CalendarDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr calendar based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["upcoming"]
    async_add_entities([SonarrCalendarEntity(coordinator, "Sonarr Episodes")])


async def get_sonarr_episode_events(
    coordinator: CalendarDataUpdateCoordinator,
) -> list[CalendarEvent]:
    """Update the list of upcoming episodes."""
    calendar_entries: list[CalendarEvent] = []
    for episode in coordinator.data:
        episode_endtime_utc = episode.airDateUtc + timedelta(
            minutes=episode.series.runtime
        )
        calendar_entries.append(
            CalendarEvent(
                summary=episode.series.title,
                description=episode.title,
                location=episode.series.network,
                start=episode.airDateUtc,
                end=episode_endtime_utc,
            )
        )
    return calendar_entries


class SonarrCalendarEntity(CalendarEntity):
    """Representation of a Sonarr Calendar element."""

    coordinator: CalendarDataUpdateCoordinator
    _events: list[CalendarEvent]

    def __init__(self, coordinator: CalendarDataUpdateCoordinator, name: str) -> None:
        """Initialize Sonarr calendar."""
        self.coordinator = coordinator
        self._attr_name = name
        self._events = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if self._events:
            return self._events[0]
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        episode_events = await get_sonarr_episode_events(self.coordinator)
        start_date = as_utc(start_date)
        end_date = as_utc(end_date)
        self._events = [
            episode
            for episode in episode_events
            if start_date <= episode.start <= end_date
        ]

        return self._events

    async def async_update(self) -> None:
        """Update the calendar for new entries."""
        episodes = await get_sonarr_episode_events(self.coordinator)
        self._events = episodes
