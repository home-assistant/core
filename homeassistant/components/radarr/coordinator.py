"""Data update coordinator for the Radarr integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Generic, TypeVar, cast

from aiopyarr import (
    Health,
    RadarrCalendarItem,
    RadarrMovie,
    RootFolder,
    SystemStatus,
    exceptions,
)
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DEFAULT_MAX_RECORDS, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import RadarrConfigEntry

T = TypeVar("T", bound=SystemStatus | list[RootFolder] | list[Health] | int | None)


@dataclass
class RadarrEventMixIn:
    """Mixin for Radarr calendar event."""

    release_type: str


@dataclass
class RadarrEvent(CalendarEvent, RadarrEventMixIn):
    """A class to describe a Radarr calendar event."""


class RadarrDataUpdateCoordinator(DataUpdateCoordinator[T], Generic[T], ABC):
    """Data update coordinator for the Radarr integration."""

    config_entry: RadarrConfigEntry
    _update_interval = timedelta(seconds=30)

    def __init__(
        self,
        hass: HomeAssistant,
        host_configuration: PyArrHostConfiguration,
        api_client: RadarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=self._update_interval,
        )
        self.api_client = api_client
        self.host_configuration = host_configuration

    async def _async_update_data(self) -> T:
        """Get the latest data from Radarr."""
        try:
            return await self._fetch_data()

        except exceptions.ArrConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError


class StatusDataUpdateCoordinator(RadarrDataUpdateCoordinator[SystemStatus]):
    """Status update coordinator for Radarr."""

    async def _fetch_data(self) -> SystemStatus:
        """Fetch the data."""
        return await self.api_client.async_get_system_status()


class DiskSpaceDataUpdateCoordinator(RadarrDataUpdateCoordinator[list[RootFolder]]):
    """Disk space update coordinator for Radarr."""

    async def _fetch_data(self) -> list[RootFolder]:
        """Fetch the data."""
        root_folders = await self.api_client.async_get_root_folders()
        if isinstance(root_folders, RootFolder):
            return [root_folders]
        return root_folders


class HealthDataUpdateCoordinator(RadarrDataUpdateCoordinator[list[Health]]):
    """Health update coordinator."""

    async def _fetch_data(self) -> list[Health]:
        """Fetch the health data."""
        health = await self.api_client.async_get_failed_health_checks()
        if isinstance(health, Health):
            return [health]
        return health


class MoviesDataUpdateCoordinator(RadarrDataUpdateCoordinator[int]):
    """Movies update coordinator."""

    async def _fetch_data(self) -> int:
        """Fetch the movies data."""
        return len(cast(list[RadarrMovie], await self.api_client.async_get_movies()))


class QueueDataUpdateCoordinator(RadarrDataUpdateCoordinator):
    """Queue update coordinator."""

    async def _fetch_data(self) -> int:
        """Fetch the movies in queue."""
        return (
            await self.api_client.async_get_queue(page_size=DEFAULT_MAX_RECORDS)
        ).totalRecords


class CalendarUpdateCoordinator(RadarrDataUpdateCoordinator[None]):
    """Calendar update coordinator."""

    _update_interval = timedelta(hours=1)

    def __init__(
        self,
        hass: HomeAssistant,
        host_configuration: PyArrHostConfiguration,
        api_client: RadarrClient,
    ) -> None:
        """Initialize."""
        super().__init__(hass, host_configuration, api_client)
        self.event: RadarrEvent | None = None
        self._events: list[RadarrEvent] = []

    async def _fetch_data(self) -> None:
        """Fetch the calendar."""
        self.event = None
        _date = dt_util.start_of_local_day()
        while self.event is None:
            await self.async_get_events(_date, _date + timedelta(days=1))
            for event in self._events:
                if event.start >= _date:
                    self.event = event
                    break
            # Prevent infinite loop in case there is nothing recent in the calendar
            if (_date - dt_util.now()).days > 45:
                break
            _date = _date + timedelta(days=1)

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[RadarrEvent]:
        """Get cached events and request missing dates."""
        # remove older events to prevent memory leak
        start = start_date.date()
        self._events = [
            e for e in self._events if e.start >= dt_util.now() - timedelta(days=30)
        ]
        _days = (end_date.date() - start).days
        await asyncio.gather(
            *(
                self._async_get_events(d)
                for d in (start + timedelta(days=x) for x in range(_days))
                if d
                not in (cast(datetime, event.start).date() for event in self._events)
            )
        )
        return self._events

    async def _async_get_events(self, _date: date) -> None:
        """Return events from specified date."""
        offset = dt_util.start_of_local_day(_date).utcoffset()
        days = timedelta(days=0 if offset and offset < timedelta() else 1)
        self._events.extend(
            _get_calendar_event(days, evt)
            for evt in await self.api_client.async_get_calendar(
                start_date=_date, end_date=_date + timedelta(days=1)
            )
            if evt.title not in (e.summary for e in self._events)
        )


def _get_calendar_event(offset: timedelta, event: RadarrCalendarItem) -> RadarrEvent:
    """Return a RadarrEvent from an API event."""
    _date, _type = event.releaseDateType()
    _dt = dt_util.start_of_local_day(_date) + offset
    return RadarrEvent(
        summary=event.title,
        start=_dt - timedelta(days=1),
        end=_dt,
        description=event.overview.replace(":", ";"),
        release_type=_type,
    )
