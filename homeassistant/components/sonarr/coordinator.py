"""Data update coordinator for the Sonarr integration."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
            update_interval=timedelta(seconds=30),
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
        """Get all events in a specific time frame."""
        episodes = cast(
            list[SonarrCalendar],
            await self.api_client.async_get_calendar(
                start_date=start_date, end_date=end_date, include_series=True
            ),
        )
        return [e for ep in episodes if (e := _get_calendar_event(ep)) is not None]


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
