"""Module for using the calendar entity platform."""

from __future__ import annotations

import datetime
import logging
from typing import Any, cast

import nextcord

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

PARALLEL_UPDATES = 2
SCAN_INTERVAL = datetime.timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the calendar entities from the configuration guilds."""
    async_add_entities(
        [
            DiscordCalendar(
                await hass.data[DOMAIN][entry.entry_id].fetch_guild(guild_id)
            )
            for guild_id in entry.data["guild_ids"]
        ],
        False,
    )
    _LOGGER.debug("Finished setting up Discord calendars")


class DiscordCalendar(CalendarEntity):
    """A :py:class:`CalendarEntity` subclass that grabs events from discord."""

    def __init__(self, guild: nextcord.Guild) -> None:
        """Initialize attributes for :py:class:`DiscordCalendar`."""
        _LOGGER.debug("Initialized calendar for %r", guild)
        self.events: list[CalendarEvent] = []
        self.guild = guild
        self.entity_id = f"calendar.discal_{guild.id}"

    @property
    def discord_client(self) -> nextcord.Client:
        """Return the shared Discord Client object."""
        assert self.platform is not None
        assert self.platform.config_entry is not None
        return cast(
            nextcord.Client,
            self.hass.data[DOMAIN][self.platform.config_entry.entry_id],
        )

    @property
    def unique_id(self) -> str:
        """Uniquely identify each calendar with the ID of its corresponding guild."""
        return str(self.guild.id)

    @property
    def name(self) -> str:
        """Display the name of the corresponding guild."""
        return self.guild.name

    @property
    def event(self) -> CalendarEvent | None:
        """Return the oldest event fetched most recently."""
        if self.events:
            return self.events[0]
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return all events known locally between two timestamps."""
        _LOGGER.debug("Events were requested between %r and %r", start_date, end_date)
        return [
            event
            for event in self.events
            if start_date <= event.start <= event.end <= end_date
        ]

    @property
    def entity_picture(self) -> str:
        """Return the Bot's profile picture to use in the frontend."""
        assert self.guild.icon is not None
        return self.guild.icon.url

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra information about the corresponding guild."""
        return {"guild_id": str(self.guild.id)}

    async def async_update(self) -> None:
        """Do the I/O to fetch guild events from the Discord API and stores the locally."""
        _LOGGER.debug("Grabbing events from Discord")
        self.events = []
        async for scheduled_event in await self.guild.fetch_scheduled_events():
            event = CalendarEvent(
                summary=scheduled_event.name,
                description=scheduled_event.description,
                location=scheduled_event.location or str(scheduled_event.channel),
                start=scheduled_event.start_time,
                end=scheduled_event.end_time
                or scheduled_event.start_time + datetime.timedelta(hours=1),
            )
            _LOGGER.debug("Initialized an event: %r", event)
            if event not in self.events:
                self.events.append(event)
        _LOGGER.debug("Grabbed events from Discord")
