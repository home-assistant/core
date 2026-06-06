"""Data update coordinator for the Sonarr integration."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TypeVar, cast

from aiopyarr import (
    Command,
    Diskspace,
    SonarrCalendar,
    SonarrQueue,
    SonarrSeries,
    SonarrWantedMissing,
    SystemStatus,
    exceptions,
)
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.sonarr_client import SonarrClient

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_UPCOMING_DAYS, CONF_WANTED_MAX_ITEMS, DOMAIN, LOGGER

SonarrDataT = TypeVar(
    "SonarrDataT",
    bound=(
        list[SonarrCalendar]
        | list[Command]
        | list[Diskspace]
        | SonarrQueue
        | list[SonarrSeries]
        | SystemStatus
        | SonarrWantedMissing
    ),
)


@dataclass
class SonarrData:
    """Sonarr data type."""

    upcoming: CalendarDataUpdateCoordinator
    commands: CommandsDataUpdateCoordinator
    diskspace: DiskSpaceDataUpdateCoordinator
    queue: QueueDataUpdateCoordinator
    series: SeriesDataUpdateCoordinator
    status: StatusDataUpdateCoordinator
    wanted: WantedDataUpdateCoordinator


type SonarrConfigEntry = ConfigEntry[SonarrData]


class SonarrDataUpdateCoordinator(DataUpdateCoordinator[SonarrDataT]):
    """Data update coordinator for the Sonarr integration."""

    config_entry: SonarrConfigEntry
    _update_interval = timedelta(seconds=30)

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SonarrConfigEntry,
        host_configuration: PyArrHostConfiguration,
        api_client: SonarrClient,
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
        self.system_version: str | None = None

    async def _async_update_data(self) -> SonarrDataT:
        """Get the latest data from Sonarr."""
        try:
            return await self._fetch_data()

        except exceptions.ArrConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex

    async def _fetch_data(self) -> SonarrDataT:
        """Fetch the actual data."""
        raise NotImplementedError


def _get_calendar_event(episode: SonarrCalendar) -> CalendarEvent | None:
    """Return a CalendarEvent from a SonarrCalendar episode."""
    if not (air_date := getattr(episode, "airDateUtc", None)):
        return None
    if air_date.tzinfo is None:
        air_date = air_date.replace(tzinfo=UTC)
    runtime = getattr(episode.series, "runtime", None) or 60
    end = air_date + timedelta(minutes=runtime)
    episode_id = f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}"
    series_title = getattr(episode.series, "title", None)
    episode_title = getattr(episode, "title", None)
    summary = " - ".join(filter(None, [series_title, episode_id, episode_title]))
    return CalendarEvent(
        summary=summary,
        start=air_date,
        end=end,
        description=getattr(episode, "overview", None) or "",
    )


class CalendarDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[SonarrCalendar]]):
    """Calendar update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SonarrConfigEntry,
        host_configuration: PyArrHostConfiguration,
        api_client: SonarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, config_entry, host_configuration, api_client)
        self.event: CalendarEvent | None = None
        self._events: list[CalendarEvent] = []
        self._fetched_dates: set[date] = set()

    async def _fetch_data(self) -> list[SonarrCalendar]:
        """Fetch the calendar data."""
        local = dt_util.start_of_local_day().replace(microsecond=0)
        start = dt_util.as_utc(local)
        end = start + timedelta(days=self.config_entry.options[CONF_UPCOMING_DAYS])
        episodes = cast(
            list[SonarrCalendar],
            await self.api_client.async_get_calendar(
                start_date=start, end_date=end, include_series=True
            ),
        )
        self.event = next(
            (e for ep in episodes if (e := _get_calendar_event(ep)) is not None),
            None,
        )
        return episodes

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get cached events and request missing dates."""
        cutoff = dt_util.now().date() - timedelta(days=30)
        self._events = [
            e
            for e in self._events
            if (e.start.date() if isinstance(e.start, datetime) else e.start) >= cutoff
        ]
        self._fetched_dates = {d for d in self._fetched_dates if d >= cutoff}
        _days = (end_date - start_date).days
        await asyncio.gather(
            *(
                self._async_get_events(d)
                for d in ((start_date + timedelta(days=x)).date() for x in range(_days))
                if d not in self._fetched_dates
            )
        )
        return self._events

    async def _async_get_events(self, _date: date) -> None:
        """Fetch events for a specific date and extend the cache."""
        _start = datetime(_date.year, _date.month, _date.day, tzinfo=UTC)
        self._events.extend(
            e
            for ep in cast(
                list[SonarrCalendar],
                await self.api_client.async_get_calendar(
                    start_date=_start,
                    end_date=_start + timedelta(days=1),
                    include_series=True,
                ),
            )
            if (e := _get_calendar_event(ep)) is not None
            and e.summary not in (ev.summary for ev in self._events)
        )
        self._fetched_dates.add(_date)


class CommandsDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[Command]]):
    """Commands update coordinator for Sonarr."""

    async def _fetch_data(self) -> list[Command]:
        """Fetch the data."""
        return cast(list[Command], await self.api_client.async_get_commands())


class DiskSpaceDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[Diskspace]]):
    """Disk space update coordinator for Sonarr."""

    async def _fetch_data(self) -> list[Diskspace]:
        """Fetch the data."""
        return await self.api_client.async_get_diskspace()


class QueueDataUpdateCoordinator(SonarrDataUpdateCoordinator[SonarrQueue]):
    """Queue update coordinator."""

    async def _fetch_data(self) -> SonarrQueue:
        """Fetch the data."""
        return await self.api_client.async_get_queue(
            include_series=True, include_episode=True
        )


class SeriesDataUpdateCoordinator(SonarrDataUpdateCoordinator[list[SonarrSeries]]):
    """Series update coordinator."""

    async def _fetch_data(self) -> list[SonarrSeries]:
        """Fetch the data."""
        return cast(list[SonarrSeries], await self.api_client.async_get_series())


class StatusDataUpdateCoordinator(SonarrDataUpdateCoordinator[SystemStatus]):
    """Status update coordinator for Sonarr."""

    async def _fetch_data(self) -> SystemStatus:
        """Fetch the data."""
        return await self.api_client.async_get_system_status()


class WantedDataUpdateCoordinator(SonarrDataUpdateCoordinator[SonarrWantedMissing]):
    """Wanted update coordinator."""

    async def _fetch_data(self) -> SonarrWantedMissing:
        """Fetch the data."""
        return await self.api_client.async_get_wanted(
            page_size=self.config_entry.options[CONF_WANTED_MAX_ITEMS],
            include_series=True,
        )
