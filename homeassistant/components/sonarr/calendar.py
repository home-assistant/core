"""Support for Sonarr calendar."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_utc, start_of_local_day

from .const import DOMAIN
from .coordinator import CalendarDataUpdateCoordinator
from .entity import SonarrEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr calendar based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["upcoming"]
    async_add_entities([SonarrCalendarEntity(coordinator, "Episodes")])


class SonarrCalendarEntity(SonarrEntity, CalendarEntity):
    """Defines a Sonarr Calendar."""

    def __init__(self, coordinator: CalendarDataUpdateCoordinator, name: str) -> None:
        """Initialize the Sonarr Calendar."""
        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="sonarr.episodes", name=name),
        )

        self._coordinator: CalendarDataUpdateCoordinator = coordinator
        self._events: list[CalendarEvent] = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._events[0] if self._events else None

    def upcoming(self) -> list[str | None]:
        """Return a list of all upcoming events."""
        return [ep.uid for ep in self._events if ep.start >= start_of_local_day()]

    def _calc_end_time(self, start_date: datetime, duration: int) -> datetime:
        """Calculate the end datetime for an episode."""
        return start_date + timedelta(minutes=duration)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        start_date = as_utc(start_date)
        end_date = as_utc(end_date)
        return [
            episode
            for episode in self._events
            if start_date <= episode.start <= end_date
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._events.extend(
            CalendarEvent(
                uid=str(episode.id),
                summary=episode.series.title,
                description=episode.title,
                location=episode.series.network,
                start=episode.airDateUtc,
                end=self._calc_end_time(episode.airDateUtc, episode.series.runtime),
            )
            for episode in self._coordinator.data
            if str(episode.id) not in self.upcoming()
        )
        coord_upcoming = [str(episode.id) for episode in self._coordinator.data]
        ids_to_remove = [
            event.uid for event in self._events if event.uid not in coord_upcoming
        ]
        for event in self._events:
            if event.uid in ids_to_remove:
                self._events.remove(event)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
