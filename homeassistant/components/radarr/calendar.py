"""Support for Radarr calendar items."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from aiopyarr import RadarrCalendarItem

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import RadarrEntity
from .const import DOMAIN
from .coordinator import RadarrDataUpdateCoordinator

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


@dataclass
class RadarrEventMixIn:
    """Mixin for Radarr calendar event."""

    release_type: str


@dataclass
class RadarrEvent(CalendarEvent, RadarrEventMixIn):
    """A class to describe a Radarr calendar event."""

    description: str


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Radarr calendar entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["disk_space"]
    async_add_entities([RadarrCalendarEntity(coordinator)], True)


class RadarrCalendarEntity(RadarrEntity, CalendarEntity):
    """A Radarr calendar entity."""

    def __init__(self, coordinator: RadarrDataUpdateCoordinator) -> None:
        """Create the Calendar event device."""
        super().__init__(coordinator, name=DOMAIN)
        self.coordinator = coordinator
        self._event: RadarrEvent | None = None
        self._events: list[RadarrEvent] = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(  # type:ignore[override]
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[RadarrEvent]:
        """Get cached events and request missing dates."""
        _days = (end_date - start_date).days
        await asyncio.gather(
            *(
                self._async_get_events(d)
                for d in ((start_date + timedelta(days=x)).date() for x in range(_days))
                if d not in (event.start for event in self._events)
            )
        )
        return self._events

    async def _async_get_events(self, _date: date) -> None:
        """Return events from specified date."""
        self._events.extend(
            _get_calendar_event(evt)
            for evt in await self.coordinator.api_client.async_get_calendar(
                start_date=_date - timedelta(days=1), end_date=_date
            )
            if evt.title not in (e.summary for e in self._events)
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest data."""
        self._event = None
        _date = datetime.today()
        attr: dict[str, list[str]] = {}
        while self._event is None:
            await self.async_get_events(self.hass, _date, _date + timedelta(days=1))
            for event in self._events:
                if event.start != _date.date():
                    break
                if attr:
                    attr["message"].append(event.summary)
                    attr["description"].append(event.description)
                    attr["release_type"].append(event.release_type)
                    continue
                attr = {
                    "message": [event.summary],
                    "description": [event.description],
                    "release_type": [event.release_type],
                }
                self._event = event
            self._attr_extra_state_attributes = attr
            _date = _date + timedelta(days=1)


def _get_calendar_event(event: RadarrCalendarItem) -> RadarrEvent:
    """Return a CalendarEvent from an API event."""
    _date, _type = event.releaseDateType()
    return RadarrEvent(
        summary=event.title,
        start=_date,
        end=_date + timedelta(days=1),
        description=event.overview.replace(":", ";"),
        release_type=_type,
    )
