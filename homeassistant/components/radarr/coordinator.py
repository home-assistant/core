"""Data update coordinator for the Radarr integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Generic, TypeVar, cast

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPCOMING_DAYS, DOMAIN, LOGGER


@dataclass(kw_only=True, slots=True)
class RadarrData:
    """Radarr data type."""

    calendar: CalendarUpdateCoordinator
    disk_space: DiskSpaceDataUpdateCoordinator
    health: HealthDataUpdateCoordinator
    movie: MoviesDataUpdateCoordinator
    queue: QueueDataUpdateCoordinator
    status: StatusDataUpdateCoordinator


type RadarrConfigEntry = ConfigEntry[RadarrData]

T = TypeVar("T", bound=SystemStatus | list[RootFolder] | list[Health] | int | None)


@dataclass
class RadarrEventMixIn:
    """Mixin for Radarr calendar event."""

    release_type: str


@dataclass
class RadarrEvent(CalendarEvent, RadarrEventMixIn):
    """A class to describe a Radarr calendar event."""


class RadarrDataUpdateCoordinator(DataUpdateCoordinator[T], ABC, Generic[T]):
    """Data update coordinator for the Radarr integration."""

    config_entry: RadarrConfigEntry
    _update_interval = timedelta(seconds=30)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RadarrConfigEntry,
        host_configuration: PyArrHostConfiguration,
        api_client: RadarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
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
    """Movies count update coordinator."""

    async def _fetch_data(self) -> int:
        """Fetch the total count of movies in Radarr."""
        return len(cast(list[RadarrMovie], await self.api_client.async_get_movies()))


class QueueDataUpdateCoordinator(RadarrDataUpdateCoordinator[int]):
    """Queue count update coordinator."""

    async def _fetch_data(self) -> int:
        """Fetch the number of movies in the download queue."""
        # page_size=1 is sufficient since we only need the totalRecords count
        return (await self.api_client.async_get_queue(page_size=1)).totalRecords


class CalendarUpdateCoordinator(RadarrDataUpdateCoordinator[None]):
    """Calendar update coordinator."""

    _update_interval = timedelta(hours=1)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RadarrConfigEntry,
        host_configuration: PyArrHostConfiguration,
        api_client: RadarrClient,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, host_configuration, api_client)
        self.event: RadarrEvent | None = None

    async def _fetch_data(self) -> None:
        """Fetch the calendar."""
        self.event = None
        start_date = datetime.today().date()
        events = await self._async_fetch_events(
            start_date, start_date + timedelta(days=DEFAULT_UPCOMING_DAYS)
        )
        for event in sorted(events, key=lambda event: event.start):
            if event.start >= start_date:
                self.event = event
                break

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[RadarrEvent]:
        """Get events in a specific time frame."""
        return await self._async_fetch_events(start_date.date(), end_date.date())

    async def _async_fetch_events(
        self, start_date: date, end_date: date
    ) -> list[RadarrEvent]:
        """Fetch calendar events for a date range."""
        return [
            _get_calendar_event(event)
            for event in await self.api_client.async_get_calendar(
                start_date=start_date, end_date=end_date
            )
        ]


def _get_calendar_event(event: RadarrCalendarItem) -> RadarrEvent:
    """Return a RadarrEvent from an API event."""
    _date, _type = event.releaseDateType()
    return RadarrEvent(
        summary=event.title,
        start=_date - timedelta(days=1),
        end=_date,
        description=event.overview.replace(":", ";"),
        release_type=_type,
    )
