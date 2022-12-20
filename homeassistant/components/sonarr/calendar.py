"""Support for Sonarr calendar."""
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CalendarDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonarr calendar based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["upcoming"]
    episodes = await get_sonarr_episode_events(coordinator)
    async_add_entities(
        [
            SonarrCalendarEntity(
                list(ep for ep in episodes), "Sonarr Episodes"  # noqa: C400
            )
        ]
    )


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
    """Representation of a Demo Calendar element."""

    def __init__(self, events: list[CalendarEvent], name: str) -> None:
        """Initialize demo calendar."""
        self._events = events
        self._attr_name = name

    @property
    def event(self) -> CalendarEvent:
        """Return the next upcoming event."""
        return self._events[0]

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return self._events
