"""Module for using the calendar entity platform."""

from __future__ import annotations

import datetime
from typing import Any

import nextcord

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

PARALLEL_UPDATES = 1
SCAN_INTERVAL = datetime.timedelta(minutes=10)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the calendar entities from the configuration guilds."""
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    async_add_entities(
        [DiscordCalendar(guild) async for guild in client.fetch_guilds()],
        False,
    )


class DiscordCalendar(CalendarEntity):
    """A :py:class:`CalendarEntity` subclass that grabs events from discord."""

    def __init__(self, guild: nextcord.Guild) -> None:
        """Initialize attributes for :py:class:`DiscordCalendar`."""
        self._guild = guild
        self._events: list[CalendarEvent] = []
        self.entity_id = f"calendar.{DOMAIN}_{guild.id}"

    @property
    def unique_id(self) -> str:
        """Uniquely identify each calendar with the ID of its corresponding guild."""
        return str(self._guild.id)

    @property
    def name(self) -> str:
        """Display the name of the corresponding guild."""
        return self._guild.name

    @property
    def event(self) -> CalendarEvent | None:
        """Return the oldest event fetched most recently."""
        if self._events:
            return self._events[0]
        return None

    @property
    def entity_picture(self) -> str:
        """Return the Bot's profile picture to use in the frontend."""
        if self._guild.icon is None:
            return ""
        return self._guild.icon.url

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra information about the corresponding guild."""
        return {"guild.id": str(self._guild.id)}

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return all events known locally between two timestamps."""
        return [
            event
            for event in self._events
            if start_date < event.start < end_date  # Start and end are exclusive.
        ]

    async def async_update(self) -> None:
        """Do the I/O to fetch guild events from the Discord API and stores the locally."""
        events = []
        async for scheduled_event in await self._guild.fetch_scheduled_events():
            event = CalendarEvent(
                summary=scheduled_event.name,
                description=scheduled_event.description,
                location=scheduled_event.location or str(scheduled_event.channel),
                start=scheduled_event.start_time,
                end=scheduled_event.end_time
                or scheduled_event.start_time + datetime.timedelta(hours=1),
            )
            events.append(event)
        self._events = events
